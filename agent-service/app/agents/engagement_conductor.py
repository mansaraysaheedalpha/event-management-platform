"""
Engagement Conductor Agent - LangGraph Workflow

Implements the full Perceive → Decide → Act → Learn agent loop using LangGraph.

Agent Modes:
- MANUAL: All interventions require human approval
- SEMI_AUTO: High-confidence interventions auto-execute, low-confidence require approval
- AUTO: All interventions auto-execute (fully autonomous)

State Flow:
    PERCEIVE (Monitor signals & detect anomalies)
         ↓
    DECIDE (Use Thompson Sampling to select intervention)
         ↓
    [Approval Gate - if needed]
         ↓
    ACT (Execute intervention)
         ↓
    LEARN (Update Thompson Sampling statistics)
         ↓
    [Loop back to PERCEIVE]
"""

import asyncio
import os
from typing import Dict, Optional, List, TypedDict, Literal
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
import logging

# LangGraph imports
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

# LangSmith tracing
from langsmith import Client
from langsmith.run_helpers import traceable

# Internal imports
from app.agents.thompson_sampling import (
    ThompsonSampling,
    InterventionType,
    AnomalyType,
    ContextKey,
    get_thompson_sampling
)
from app.agents.intervention_selector import InterventionRecommendation
from app.agents.intervention_executor import InterventionExecutor
from app.models.anomaly import Anomaly
from app.db.timescale import AsyncSessionLocal
from app.core.redis_client import redis_client
import json

logger = logging.getLogger(__name__)

# Configure LangSmith tracing
LANGSMITH_ENABLED = os.getenv("LANGSMITH_TRACING", "false").lower() == "true"
LANGSMITH_PROJECT = os.getenv("LANGSMITH_PROJECT", "engagement-conductor")

if LANGSMITH_ENABLED:
    os.environ["LANGCHAIN_TRACING_V2"] = "true"
    os.environ["LANGCHAIN_PROJECT"] = LANGSMITH_PROJECT
    logger.info(f"LangSmith tracing enabled for project: {LANGSMITH_PROJECT}")
else:
    logger.info("LangSmith tracing disabled")


class AgentMode(str, Enum):
    """Agent operating modes"""
    MANUAL = "MANUAL"           # All interventions require approval
    SEMI_AUTO = "SEMI_AUTO"     # High-confidence auto-execute
    AUTO = "AUTO"               # Fully autonomous


class AgentStatus(str, Enum):
    """Agent status indicators"""
    MONITORING = "MONITORING"               # Watching signals, no anomaly
    ANOMALY_DETECTED = "ANOMALY_DETECTED"   # Anomaly found, deciding action
    WAITING_APPROVAL = "WAITING_APPROVAL"   # Waiting for human approval
    INTERVENING = "INTERVENING"             # Executing intervention
    LEARNING = "LEARNING"                   # Updating statistics
    IDLE = "IDLE"                           # Not active


# LangGraph State
class AgentState(TypedDict):
    """State passed through the LangGraph workflow"""
    # Session context
    session_id: str
    event_id: str
    session_context: Dict

    # Current signals
    engagement_score: float
    active_users: int
    signals: Dict

    # Anomaly detection
    anomaly: Optional[Anomaly]
    anomaly_detected: bool

    # Decision making
    context: Optional[ContextKey]
    selected_intervention: Optional[InterventionType]
    intervention_recommendation: Optional[InterventionRecommendation]
    confidence: float

    # Agent control
    agent_mode: AgentMode
    requires_approval: bool
    approved: bool

    # Execution
    intervention_id: Optional[str]
    execution_result: Optional[Dict]

    # Learning
    success: bool
    reward: float

    # Status
    status: AgentStatus
    timestamp: str

    # Decision explanation
    explanation: str


@dataclass
class AgentDecision:
    """Structured decision output from the agent"""
    intervention_type: InterventionType
    confidence: float
    context: ContextKey
    reasoning: str
    requires_approval: bool
    timestamp: datetime


class EngagementConductorAgent:
    """
    LangGraph-based engagement conductor agent.

    Implements full Perceive → Decide → Act → Learn cycle with support for
    three operating modes (Manual, Semi-Auto, Auto).
    """

    # Confidence threshold for semi-auto mode
    AUTO_APPROVE_THRESHOLD = 0.75

    def __init__(
        self,
        thompson_sampling: Optional[ThompsonSampling] = None,
        intervention_executor: Optional[InterventionExecutor] = None
    ):
        """
        Initialize engagement conductor agent.

        Args:
            thompson_sampling: Thompson Sampling instance (creates new if None)
            intervention_executor: Intervention executor (creates new if None)
        """
        self.thompson_sampling = thompson_sampling or get_thompson_sampling()
        self.intervention_executor = intervention_executor or InterventionExecutor()

        # Build LangGraph workflow
        self.workflow = self._build_workflow()

        # Compile with memory for state persistence
        self.memory = MemorySaver()
        self.app = self.workflow.compile(checkpointer=self.memory)

        # Track active decisions awaiting approval
        self.pending_approvals: Dict[str, AgentState] = {}

        logger.info("EngagementConductorAgent initialized with LangGraph workflow")

    async def _publish_agent_event(
        self,
        event_type: str,
        session_id: str,
        data: Dict
    ):
        """
        Publish agent state event to Redis for WebSocket forwarding.

        Args:
            event_type: Event type (agent.status, agent.decision, agent.intervention.executed)
            session_id: Session ID
            data: Event data
        """
        try:
            event = {
                "type": event_type,
                "session_id": session_id,
                "timestamp": datetime.utcnow().isoformat(),
                "data": data
            }

            # Publish to Redis channel for real-time service
            channel = f"session:{session_id}:events"
            await redis_client.publish(channel, json.dumps(event))

            logger.debug(f"Published {event_type} event for session {session_id}")

        except Exception as e:
            logger.error(f"Failed to publish agent event: {e}")

    def _build_workflow(self) -> StateGraph:
        """Build the LangGraph state machine"""

        workflow = StateGraph(AgentState)

        # Define nodes (agent steps)
        workflow.add_node("perceive", self._perceive_node)
        workflow.add_node("decide", self._decide_node)
        workflow.add_node("check_approval", self._check_approval_node)
        workflow.add_node("wait_approval", self._wait_approval_node)
        workflow.add_node("act", self._act_node)
        workflow.add_node("learn", self._learn_node)

        # Define edges (state transitions)
        workflow.set_entry_point("perceive")

        # Perceive → Decide (if anomaly) or END
        workflow.add_conditional_edges(
            "perceive",
            self._should_decide,
            {
                True: "decide",
                False: END
            }
        )

        # Decide → Check Approval
        workflow.add_edge("decide", "check_approval")

        # Check Approval → Wait (if needed) or Act (if auto-approved)
        workflow.add_conditional_edges(
            "check_approval",
            self._should_wait_approval,
            {
                True: "wait_approval",
                False: "act"
            }
        )

        # Wait Approval → Act (once approved) or END (if dismissed)
        workflow.add_conditional_edges(
            "wait_approval",
            self._check_approval_status,
            {
                "approved": "act",
                "dismissed": END
            }
        )

        # Act → Learn
        workflow.add_edge("act", "learn")

        # Learn → END
        workflow.add_edge("learn", END)

        return workflow

    # ==================== WORKFLOW NODES ====================

    @traceable(name="perceive", project_name=LANGSMITH_PROJECT)
    async def _perceive_node(self, state: AgentState) -> AgentState:
        """
        PERCEIVE: Monitor signals and detect anomalies.

        This node receives current engagement signals and checks if an
        anomaly is present that warrants intervention.
        """
        logger.info(f"[PERCEIVE] Session {state['session_id']}: "
                   f"engagement={state['engagement_score']:.1f}, "
                   f"users={state['active_users']}")

        state["status"] = AgentStatus.MONITORING

        # Check if anomaly detected
        if state.get("anomaly"):
            logger.info(f"[PERCEIVE] Anomaly detected: {state['anomaly'].anomaly_type}")
            state["anomaly_detected"] = True
            state["status"] = AgentStatus.ANOMALY_DETECTED
        else:
            state["anomaly_detected"] = False

        state["timestamp"] = datetime.utcnow().isoformat()

        # Publish status update
        await self._publish_agent_event(
            event_type="agent.status",
            session_id=state["session_id"],
            data={"status": state["status"].value}
        )

        return state

    @traceable(name="decide", project_name=LANGSMITH_PROJECT)
    async def _decide_node(self, state: AgentState) -> AgentState:
        """
        DECIDE: Use Thompson Sampling to select best intervention.

        Uses reinforcement learning to choose the intervention most likely
        to succeed in the current context.
        """
        logger.info(f"[DECIDE] Session {state['session_id']}: Selecting intervention")

        anomaly = state["anomaly"]

        # Create context for Thompson Sampling
        context = self.thompson_sampling.create_context(
            anomaly_type=AnomalyType(anomaly.anomaly_type),
            engagement_score=state["engagement_score"],
            active_users=state["active_users"]
        )

        # Select intervention using Thompson Sampling
        intervention_type, sampled_value = self.thompson_sampling.select_intervention(context)

        # Get expected success rate for confidence
        stats = self.thompson_sampling.get_stats(context, intervention_type)
        confidence = stats.success_rate if stats else 0.5

        # Generate reasoning
        reasoning = self._generate_reasoning(
            intervention_type=intervention_type,
            context=context,
            confidence=confidence,
            anomaly=anomaly
        )

        # Update state
        state["context"] = context
        state["selected_intervention"] = intervention_type
        state["confidence"] = confidence
        state["explanation"] = reasoning

        logger.info(
            f"[DECIDE] Selected {intervention_type} with confidence {confidence:.2f}"
        )

        # Publish decision event
        await self._publish_agent_event(
            event_type="agent.decision",
            session_id=state["session_id"],
            data={
                "decision": {
                    "interventionType": intervention_type.value,
                    "confidence": confidence,
                    "reasoning": reasoning,
                    "context": {
                        "engagement_bucket": context.engagement_bucket,
                        "session_size_bucket": context.session_size_bucket,
                        "anomaly_type": context.anomaly_type.value
                    },
                    "historicalPerformance": {
                        "successRate": stats.success_rate if stats else 0.0,
                        "totalAttempts": stats.total_attempts if stats else 0,
                        "isExploring": stats.total_attempts < 5 if stats else True
                    },
                    "autoApproved": False,  # Will be updated in check_approval
                    "timestamp": datetime.utcnow().isoformat()
                }
            }
        )

        return state

    async def _check_approval_node(self, state: AgentState) -> AgentState:
        """
        Check if approval is needed based on agent mode and confidence.
        """
        agent_mode = state["agent_mode"]
        confidence = state["confidence"]

        if agent_mode == AgentMode.AUTO:
            # Fully autonomous - no approval needed
            state["requires_approval"] = False
            state["approved"] = True
            logger.info(f"[APPROVAL] AUTO mode - intervention auto-approved")

        elif agent_mode == AgentMode.SEMI_AUTO:
            # Semi-autonomous - auto-approve if confidence is high
            if confidence >= self.AUTO_APPROVE_THRESHOLD:
                state["requires_approval"] = False
                state["approved"] = True
                logger.info(
                    f"[APPROVAL] SEMI_AUTO mode - high confidence "
                    f"({confidence:.2f}) - auto-approved"
                )
            else:
                state["requires_approval"] = True
                state["approved"] = False
                state["status"] = AgentStatus.WAITING_APPROVAL
                logger.info(
                    f"[APPROVAL] SEMI_AUTO mode - low confidence "
                    f"({confidence:.2f}) - requires approval"
                )

        else:  # MANUAL
            # Manual mode - always require approval
            state["requires_approval"] = True
            state["approved"] = False
            state["status"] = AgentStatus.WAITING_APPROVAL
            logger.info(f"[APPROVAL] MANUAL mode - requires approval")

        return state

    async def _wait_approval_node(self, state: AgentState) -> AgentState:
        """
        WAIT: Pause execution until human approves or dismisses.

        This is a blocking node that stores state and waits for external
        approval via the approve_intervention() method.
        """
        session_id = state["session_id"]

        logger.info(f"[WAIT] Session {session_id}: Waiting for approval")

        # Store state for later retrieval
        self.pending_approvals[session_id] = state

        # Publish waiting for approval status
        await self._publish_agent_event(
            event_type="agent.status",
            session_id=session_id,
            data={"status": AgentStatus.WAITING_APPROVAL.value}
        )

        # This node will be resumed by external call to approve_intervention()
        return state

    @traceable(name="act", project_name=LANGSMITH_PROJECT)
    async def _act_node(self, state: AgentState) -> AgentState:
        """
        ACT: Execute the selected intervention.

        Calls the intervention executor to launch polls, send prompts, etc.
        """
        logger.info(
            f"[ACT] Session {state['session_id']}: "
            f"Executing {state['selected_intervention']}"
        )

        state["status"] = AgentStatus.INTERVENING

        try:
            # Create InterventionRecommendation from state
            recommendation = InterventionRecommendation(
                intervention_type=state["selected_intervention"].value,
                priority="HIGH",
                confidence=state["confidence"],
                reason=state["explanation"],
                context={
                    "session_id": state["session_id"],
                    "event_id": state["event_id"],
                    "anomaly_type": state["anomaly"].anomaly_type if state["anomaly"] else "UNKNOWN",
                    "signals": state["signals"],
                    "timing": "IMMEDIATE"
                },
                estimated_impact=state["confidence"]
            )

            # Execute intervention with database session
            async with AsyncSessionLocal() as db:
                result = await self.intervention_executor.execute(
                    recommendation=recommendation,
                    db_session=db,
                    session_context=state["session_context"]
                )

            state["intervention_id"] = result.get("intervention_id")
            state["execution_result"] = result
            state["success"] = result.get("success", False)

            logger.info(f"[ACT] Intervention executed: {state['intervention_id']}")

            # Publish intervention executed event
            await self._publish_agent_event(
                event_type="agent.intervention.executed",
                session_id=state["session_id"],
                data={
                    "intervention_id": state["intervention_id"],
                    "intervention_type": state["selected_intervention"].value,
                    "success": state["success"],
                    "result": state["execution_result"]
                }
            )

        except Exception as e:
            logger.error(f"[ACT] Execution failed: {e}", exc_info=True)
            state["success"] = False
            state["execution_result"] = {"error": str(e)}

        return state

    @traceable(name="learn", project_name=LANGSMITH_PROJECT)
    async def _learn_node(self, state: AgentState) -> AgentState:
        """
        LEARN: Update Thompson Sampling statistics based on outcome.

        This completes the reinforcement learning loop by updating our
        belief about which interventions work best.
        """
        logger.info(f"[LEARN] Session {state['session_id']}: Updating statistics")

        state["status"] = AgentStatus.LEARNING

        # Calculate reward based on outcome
        # TODO: In production, measure actual engagement delta after intervention
        if state["success"]:
            # Simple reward: 1.0 for success, 0.0 for failure
            # In practice, this should be the engagement improvement (0-1)
            reward = 1.0
        else:
            reward = 0.0

        state["reward"] = reward

        # Update Thompson Sampling
        self.thompson_sampling.update(
            context=state["context"],
            intervention_type=state["selected_intervention"],
            success=state["success"],
            reward=reward
        )

        logger.info(
            f"[LEARN] Updated statistics: success={state['success']}, "
            f"reward={reward:.2f}"
        )

        # Export updated stats (for persistence)
        stats_export = self.thompson_sampling.export_stats()

        # TODO: Persist to database for long-term learning

        return state

    # ==================== CONDITIONAL EDGES ====================

    def _should_decide(self, state: AgentState) -> bool:
        """Should we proceed to decision making?"""
        return state.get("anomaly_detected", False)

    def _should_wait_approval(self, state: AgentState) -> bool:
        """Should we wait for approval?"""
        return state.get("requires_approval", False)

    def _check_approval_status(self, state: AgentState) -> Literal["approved", "dismissed"]:
        """Check if intervention was approved or dismissed"""
        return "approved" if state.get("approved", False) else "dismissed"

    # ==================== PUBLIC API ====================

    @traceable(name="agent_run", project_name=LANGSMITH_PROJECT)
    async def run(
        self,
        session_id: str,
        event_id: str,
        engagement_score: float,
        active_users: int,
        signals: Dict,
        anomaly: Optional[Anomaly],
        session_context: Dict,
        agent_mode: AgentMode = AgentMode.MANUAL
    ) -> AgentState:
        """
        Run the agent loop for a single anomaly.

        Args:
            session_id: Session ID
            event_id: Event ID
            engagement_score: Current engagement score
            active_users: Number of active users
            signals: Current engagement signals
            anomaly: Detected anomaly (None if just monitoring)
            session_context: Session metadata (title, topic, etc.)
            agent_mode: Operating mode (MANUAL, SEMI_AUTO, AUTO)

        Returns:
            Final agent state after execution
        """
        # Create initial state
        initial_state: AgentState = {
            "session_id": session_id,
            "event_id": event_id,
            "session_context": session_context,
            "engagement_score": engagement_score,
            "active_users": active_users,
            "signals": signals,
            "anomaly": anomaly,
            "anomaly_detected": anomaly is not None,
            "context": None,
            "selected_intervention": None,
            "intervention_recommendation": None,
            "confidence": 0.0,
            "agent_mode": agent_mode,
            "requires_approval": False,
            "approved": False,
            "intervention_id": None,
            "execution_result": None,
            "success": False,
            "reward": 0.0,
            "status": AgentStatus.IDLE,
            "timestamp": datetime.utcnow().isoformat(),
            "explanation": ""
        }

        # Run workflow
        config = {"configurable": {"thread_id": session_id}}
        final_state = await self.app.ainvoke(initial_state, config)

        return final_state

    async def approve_intervention(self, session_id: str, approved: bool):
        """
        Approve or dismiss a pending intervention.

        Args:
            session_id: Session ID
            approved: True to approve, False to dismiss
        """
        if session_id not in self.pending_approvals:
            raise ValueError(f"No pending approval for session {session_id}")

        state = self.pending_approvals[session_id]
        state["approved"] = approved

        if approved:
            logger.info(f"[APPROVAL] Session {session_id}: Intervention approved")
            # Continue workflow from wait_approval node
            config = {"configurable": {"thread_id": session_id}}
            final_state = await self.app.ainvoke(state, config)
            return final_state
        else:
            logger.info(f"[APPROVAL] Session {session_id}: Intervention dismissed")
            # Remove from pending
            del self.pending_approvals[session_id]
            return state

    def get_pending_approval(self, session_id: str) -> Optional[AgentDecision]:
        """Get pending approval for a session"""
        if session_id not in self.pending_approvals:
            return None

        state = self.pending_approvals[session_id]

        return AgentDecision(
            intervention_type=state["selected_intervention"],
            confidence=state["confidence"],
            context=state["context"],
            reasoning=state["explanation"],
            requires_approval=state["requires_approval"],
            timestamp=datetime.fromisoformat(state["timestamp"])
        )

    # ==================== API METHODS ====================

    async def set_mode(self, mode: AgentMode):
        """
        Change agent operating mode.

        Args:
            mode: New agent mode (MANUAL, SEMI_AUTO, AUTO)
        """
        logger.info(f"Agent mode changed to {mode.value}")
        # Mode is passed per-run in the run() method, so this is just for logging
        # The actual mode will be set when run() is called

    async def get_state(self) -> Dict:
        """
        Get current agent state.

        Returns:
            Dict with current mode, status, and decision info
        """
        # Since agents are stateless between runs, we check pending approvals
        pending = list(self.pending_approvals.values())

        if pending:
            latest = pending[0]
            return {
                "mode": latest["agent_mode"].value,
                "status": latest["status"].value,
                "last_activity": latest["timestamp"],
                "confidence_score": latest.get("confidence"),
                "current_decision": {
                    "intervention_type": latest["selected_intervention"].value,
                    "confidence": latest["confidence"],
                    "reasoning": latest.get("explanation"),
                    "requires_approval": latest["requires_approval"],
                } if latest.get("selected_intervention") else None
            }

        return {
            "mode": "MANUAL",
            "status": "MONITORING",
            "last_activity": None,
            "confidence_score": None,
            "current_decision": None
        }

    async def approve_decision(self, decision_id: str) -> Dict:
        """
        Approve a pending decision.

        Args:
            decision_id: Decision/session ID

        Returns:
            Execution result
        """
        result = await self.approve_intervention(decision_id, approved=True)
        return {
            "success": result is not None,
            "result": result
        }

    async def reject_decision(self, decision_id: str, reason: Optional[str] = None):
        """
        Reject a pending decision.

        Args:
            decision_id: Decision/session ID
            reason: Optional rejection reason
        """
        logger.info(f"Decision {decision_id} rejected. Reason: {reason or 'Not specified'}")
        await self.approve_intervention(decision_id, approved=False)

    # ==================== HELPER METHODS ====================

    def _generate_reasoning(
        self,
        intervention_type: InterventionType,
        context: ContextKey,
        confidence: float,
        anomaly: Anomaly
    ) -> str:
        """Generate human-readable reasoning for the decision"""

        reasoning_parts = []

        # Anomaly context
        reasoning_parts.append(
            f"Detected {anomaly.anomaly_type} anomaly with {anomaly.severity} severity."
        )

        # Selected intervention
        reasoning_parts.append(
            f"Thompson Sampling selected {intervention_type} intervention "
            f"with {confidence:.0%} confidence."
        )

        # Context
        reasoning_parts.append(
            f"Context: {context.engagement_bucket} engagement, "
            f"{context.session_size_bucket} session size."
        )

        # Historical performance
        stats = self.thompson_sampling.get_stats(context, intervention_type)
        if stats and stats.total_attempts > 0:
            reasoning_parts.append(
                f"Historical success rate in similar contexts: "
                f"{stats.success_rate:.0%} ({stats.total_attempts} attempts)."
            )
        else:
            reasoning_parts.append(
                "No historical data for this context - exploring new strategy."
            )

        return " ".join(reasoning_parts)


# Global agent instance
_agent_instance: Optional[EngagementConductorAgent] = None


def get_engagement_conductor() -> EngagementConductorAgent:
    """Get or create global agent instance"""
    global _agent_instance
    if _agent_instance is None:
        _agent_instance = EngagementConductorAgent()
    return _agent_instance
