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
from typing import Dict, Optional, List, TypedDict, Literal, Tuple
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
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
from app.core.config import get_settings
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
    pre_intervention_engagement: float  # Engagement score before intervention
    post_intervention_engagement: Optional[float]  # Engagement score after delay

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

    RELIABILITY: Pending approvals are persisted to Redis to survive service restarts.
    This ensures no approval requests are lost during deployments or crashes.
    """

    # Redis key prefix for pending approvals
    PENDING_APPROVAL_KEY_PREFIX = "agent:pending_approval:"
    PENDING_APPROVAL_INDEX_KEY = "agent:pending_approvals:index"

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)

    @property
    def AUTO_APPROVE_THRESHOLD(self) -> float:
        """Confidence threshold for semi-auto mode (from config)"""
        return get_settings().AGENT_AUTO_APPROVE_THRESHOLD

    @property
    def PENDING_APPROVAL_TTL_SECONDS(self) -> int:
        """TTL for pending approvals in seconds (from config)"""
        return get_settings().AGENT_PENDING_APPROVAL_TTL_SECONDS

    @property
    def MAX_PENDING_APPROVALS(self) -> int:
        """Maximum pending approvals to prevent memory exhaustion (from config)"""
        return get_settings().AGENT_MAX_PENDING_APPROVALS

    # Delayed reward measurement configuration
    REWARD_MEASUREMENT_DELAY_SECONDS = 60  # Wait 60 seconds after intervention to measure impact
    REWARD_MEASUREMENT_TTL_SECONDS = 300   # Max time to wait for reward measurement (5 minutes)

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

        # Local cache for pending approvals (backed by Redis for persistence)
        # Format: {session_id: (AgentState, created_at)}
        self._pending_approvals_cache: Dict[str, Tuple[AgentState, datetime]] = {}

        # Pending reward measurements - interventions awaiting engagement delta calculation
        # Format: {intervention_id: (AgentState, scheduled_measurement_time)}
        self._pending_rewards: Dict[str, Tuple[AgentState, datetime]] = {}

        # Start background cleanup task
        self._cleanup_task: Optional[asyncio.Task] = None

        # Background task for delayed reward measurement
        self._reward_measurement_task: Optional[asyncio.Task] = None

        # Store current agent mode (default to MANUAL)
        self._current_mode: AgentMode = AgentMode.MANUAL

        logger.info("EngagementConductorAgent initialized with LangGraph workflow and Redis persistence")

    @property
    def pending_approvals(self) -> Dict[str, AgentState]:
        """Get pending approvals dict (for backwards compatibility - uses local cache)."""
        return {k: v[0] for k, v in self._pending_approvals_cache.items()}

    async def start_cleanup_task(self):
        """Start the background cleanup task for expired pending approvals."""
        if self._cleanup_task is None or self._cleanup_task.done():
            # Load existing pending approvals from Redis on startup
            await self._load_pending_approvals_from_redis()
            self._cleanup_task = asyncio.create_task(self._cleanup_expired_approvals())
            logger.info("Started pending approvals cleanup task")

        # Also start reward measurement task
        await self.start_reward_measurement_task()

    async def stop_cleanup_task(self):
        """Stop the background cleanup task."""
        if self._cleanup_task and not self._cleanup_task.done():
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
            logger.info("Stopped pending approvals cleanup task")

        # Also stop reward measurement task
        if self._reward_measurement_task and not self._reward_measurement_task.done():
            self._reward_measurement_task.cancel()
            try:
                await self._reward_measurement_task
            except asyncio.CancelledError:
                pass
            logger.info("Stopped reward measurement task")

    async def start_reward_measurement_task(self):
        """Start the background task for delayed reward measurement."""
        if self._reward_measurement_task is None or self._reward_measurement_task.done():
            self._reward_measurement_task = asyncio.create_task(self._measure_delayed_rewards())
            logger.info("Started delayed reward measurement task")

    async def _measure_delayed_rewards(self):
        """
        Background task that measures engagement delta after interventions.

        Waits for REWARD_MEASUREMENT_DELAY_SECONDS after each intervention,
        then fetches the current engagement score and calculates the reward.
        """
        while True:
            try:
                await asyncio.sleep(10)  # Check every 10 seconds
                now = datetime.now(timezone.utc)
                completed = []

                for intervention_id, (state, scheduled_time) in list(self._pending_rewards.items()):
                    # Check if it's time to measure
                    if now >= scheduled_time:
                        try:
                            await self._complete_reward_measurement(intervention_id, state)
                            completed.append(intervention_id)
                        except Exception as e:
                            logger.error(f"Error measuring reward for {intervention_id}: {e}")
                            # Check if expired
                            age = (now - scheduled_time).total_seconds()
                            if age > self.REWARD_MEASUREMENT_TTL_SECONDS:
                                logger.warning(f"Reward measurement expired for {intervention_id}, removing")
                                completed.append(intervention_id)

                # Remove completed measurements
                for intervention_id in completed:
                    if intervention_id in self._pending_rewards:
                        del self._pending_rewards[intervention_id]

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in reward measurement loop: {e}")

    async def _complete_reward_measurement(self, intervention_id: str, state: AgentState):
        """
        Complete reward measurement by fetching current engagement and updating Thompson Sampling.

        Reward calculation:
        - If post_engagement > pre_engagement: reward = min(delta / 0.2, 1.0) (normalized improvement)
        - If engagement maintained (delta >= -0.05): reward = 0.5 (partial success)
        - If engagement declined: reward = 0.0 (failure)

        Args:
            intervention_id: ID of the intervention
            state: Agent state containing pre-intervention data
        """
        session_id = state["session_id"]
        pre_engagement = state.get("pre_intervention_engagement", state["engagement_score"])

        # Fetch current engagement from Redis
        post_engagement = await self._fetch_current_engagement(session_id)

        if post_engagement is None:
            logger.warning(f"Could not fetch engagement for session {session_id}, using execution success only")
            # Fall back to binary reward based on execution success
            reward = 1.0 if state.get("success", False) else 0.0
        else:
            # Calculate engagement delta
            delta = post_engagement - pre_engagement

            if delta > 0:
                # Improvement - normalize to 0-1 range (assume 20% improvement = max reward)
                reward = min(delta / 0.2, 1.0)
                logger.info(
                    f"[REWARD] Session {session_id}: Engagement improved by {delta:.2%}, "
                    f"reward={reward:.2f}"
                )
            elif delta >= -0.05:
                # Engagement maintained (within 5% tolerance) - partial success
                reward = 0.5
                logger.info(
                    f"[REWARD] Session {session_id}: Engagement maintained (delta={delta:.2%}), "
                    f"reward=0.5"
                )
            else:
                # Engagement declined despite intervention
                reward = 0.0
                logger.info(
                    f"[REWARD] Session {session_id}: Engagement declined by {abs(delta):.2%}, "
                    f"reward=0.0"
                )

        # Update Thompson Sampling with actual reward
        context = state.get("context")
        intervention_type = state.get("selected_intervention")

        if context and intervention_type:
            self.thompson_sampling.update(
                context=context,
                intervention_type=intervention_type,
                success=reward > 0.3,  # Consider success if reward > 0.3
                reward=reward
            )

            logger.info(
                f"[REWARD] Updated Thompson Sampling for {intervention_type.value}: "
                f"reward={reward:.2f}, success={reward > 0.3}"
            )

            # Persist Thompson Sampling stats
            try:
                await self.thompson_sampling.save_to_redis()
            except Exception as e:
                logger.error(f"Failed to persist Thompson Sampling after reward update: {e}")

        # Publish reward measurement event
        await self._publish_agent_event(
            event_type="agent.reward.measured",
            session_id=session_id,
            data={
                "intervention_id": intervention_id,
                "pre_engagement": pre_engagement,
                "post_engagement": post_engagement,
                "reward": reward,
                "delta": post_engagement - pre_engagement if post_engagement else None
            }
        )

    async def _fetch_current_engagement(self, session_id: str) -> Optional[float]:
        """
        Fetch the current engagement score for a session from Redis.

        Args:
            session_id: Session ID

        Returns:
            Current engagement score (0-1) or None if not available
        """
        try:
            if redis_client is None:
                return None

            # Try to get latest engagement from Redis stream
            key = f"engagement:{session_id}:latest"
            data = await redis_client.client.get(key)

            if data:
                engagement_data = json.loads(data)
                return engagement_data.get("score")

            # Fallback: try to get from engagement update channel
            # This might be stale, but better than nothing
            return None

        except Exception as e:
            logger.error(f"Error fetching engagement for session {session_id}: {e}")
            return None

    def _schedule_reward_measurement(self, state: AgentState):
        """
        Schedule delayed reward measurement for an intervention.

        Args:
            state: Agent state after intervention execution
        """
        intervention_id = state.get("intervention_id")
        if not intervention_id:
            logger.warning("Cannot schedule reward measurement: no intervention_id in state")
            return

        # Store pre-intervention engagement in state
        state["pre_intervention_engagement"] = state["engagement_score"]

        # Schedule measurement after delay
        scheduled_time = datetime.now(timezone.utc) + timedelta(
            seconds=self.REWARD_MEASUREMENT_DELAY_SECONDS
        )
        self._pending_rewards[intervention_id] = (state.copy(), scheduled_time)

        logger.info(
            f"[REWARD] Scheduled reward measurement for intervention {intervention_id[:8]}... "
            f"at {scheduled_time.isoformat()}"
        )

    async def _load_pending_approvals_from_redis(self):
        """Load pending approvals from Redis on startup for crash recovery."""
        try:
            if redis_client is None:
                logger.warning("Redis client not available, skipping pending approvals recovery")
                return

            # Get all pending approval keys
            keys = await redis_client.client.keys(f"{self.PENDING_APPROVAL_KEY_PREFIX}*")
            loaded_count = 0

            for key in keys:
                try:
                    data = await redis_client.client.get(key)
                    if data:
                        approval_data = json.loads(data)
                        session_id = approval_data.get("session_id")
                        created_at = datetime.fromisoformat(approval_data.get("created_at"))
                        state = self._deserialize_state(approval_data.get("state"))

                        # Check if still valid
                        age = (datetime.now(timezone.utc) - created_at).total_seconds()
                        if age <= self.PENDING_APPROVAL_TTL_SECONDS:
                            self._pending_approvals_cache[session_id] = (state, created_at)
                            loaded_count += 1
                        else:
                            # Expired, delete from Redis
                            await redis_client.client.delete(key)

                except Exception as e:
                    logger.error(f"Error loading pending approval from Redis key {key}: {e}")

            if loaded_count > 0:
                logger.info(f"Recovered {loaded_count} pending approvals from Redis")

        except Exception as e:
            logger.error(f"Error loading pending approvals from Redis: {e}")

    async def _cleanup_expired_approvals(self):
        """Background task to clean up expired pending approvals from cache and Redis."""
        while True:
            try:
                await asyncio.sleep(60)  # Check every minute
                now = datetime.now(timezone.utc)
                expired = []

                # Check local cache
                for session_id, (state, created_at) in list(self._pending_approvals_cache.items()):
                    age = (now - created_at).total_seconds()
                    if age > self.PENDING_APPROVAL_TTL_SECONDS:
                        expired.append(session_id)

                for session_id in expired:
                    logger.info(
                        f"Cleaning up expired pending approval for session {session_id} "
                        f"(TTL exceeded: {self.PENDING_APPROVAL_TTL_SECONDS}s)"
                    )
                    # Remove from cache
                    if session_id in self._pending_approvals_cache:
                        del self._pending_approvals_cache[session_id]
                    # Remove from Redis
                    await self._remove_pending_approval_from_redis(session_id)

                if expired:
                    logger.info(f"Cleaned up {len(expired)} expired pending approvals")

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in pending approvals cleanup: {e}")

    def _serialize_state(self, state: AgentState) -> Dict:
        """Serialize AgentState for Redis storage."""
        serialized = {}
        for key, value in state.items():
            if isinstance(value, Enum):
                serialized[key] = {"_enum": type(value).__name__, "value": value.value}
            elif isinstance(value, datetime):
                serialized[key] = {"_datetime": value.isoformat()}
            elif hasattr(value, '__dict__'):
                # Handle dataclasses and custom objects
                serialized[key] = {"_object": type(value).__name__, "data": value.__dict__}
            else:
                serialized[key] = value
        return serialized

    def _deserialize_state(self, data: Dict) -> AgentState:
        """Deserialize AgentState from Redis storage."""
        deserialized = {}
        enum_map = {
            "AgentMode": AgentMode,
            "AgentStatus": AgentStatus,
            "InterventionType": InterventionType,
            "AnomalyType": AnomalyType,
        }

        for key, value in data.items():
            if isinstance(value, dict):
                if "_enum" in value:
                    enum_class = enum_map.get(value["_enum"])
                    if enum_class:
                        deserialized[key] = enum_class(value["value"])
                    else:
                        deserialized[key] = value["value"]
                elif "_datetime" in value:
                    deserialized[key] = datetime.fromisoformat(value["_datetime"])
                elif "_object" in value:
                    # For now, store as dict - full reconstruction would need object registry
                    deserialized[key] = value.get("data", value)
                else:
                    deserialized[key] = value
            else:
                deserialized[key] = value
        return deserialized

    async def _add_pending_approval(self, session_id: str, state: AgentState):
        """Add a pending approval with TTL tracking, size limit enforcement, and Redis persistence."""
        # Enforce max size limit
        if len(self._pending_approvals_cache) >= self.MAX_PENDING_APPROVALS:
            # Remove oldest approval
            oldest_session = min(
                self._pending_approvals_cache.keys(),
                key=lambda k: self._pending_approvals_cache[k][1]
            )
            logger.warning(
                f"Max pending approvals reached ({self.MAX_PENDING_APPROVALS}). "
                f"Removing oldest: {oldest_session}"
            )
            del self._pending_approvals_cache[oldest_session]
            await self._remove_pending_approval_from_redis(oldest_session)

        created_at = datetime.now(timezone.utc)
        self._pending_approvals_cache[session_id] = (state, created_at)

        # Persist to Redis with TTL
        await self._save_pending_approval_to_redis(session_id, state, created_at)

    async def _save_pending_approval_to_redis(
        self,
        session_id: str,
        state: AgentState,
        created_at: datetime
    ):
        """Persist pending approval to Redis."""
        try:
            if redis_client is None:
                return

            key = f"{self.PENDING_APPROVAL_KEY_PREFIX}{session_id}"
            data = {
                "session_id": session_id,
                "created_at": created_at.isoformat(),
                "state": self._serialize_state(state)
            }

            # Set with TTL
            await redis_client.client.setex(
                key,
                self.PENDING_APPROVAL_TTL_SECONDS,
                json.dumps(data, default=str)
            )
            logger.debug(f"Persisted pending approval to Redis: {session_id}")

        except Exception as e:
            logger.error(f"Failed to persist pending approval to Redis: {e}")

    async def _remove_pending_approval_from_redis(self, session_id: str):
        """Remove pending approval from Redis."""
        try:
            if redis_client is None:
                return

            key = f"{self.PENDING_APPROVAL_KEY_PREFIX}{session_id}"
            await redis_client.client.delete(key)
            logger.debug(f"Removed pending approval from Redis: {session_id}")

        except Exception as e:
            logger.error(f"Failed to remove pending approval from Redis: {e}")

    async def _get_pending_approval(self, session_id: str) -> Optional[AgentState]:
        """Get a pending approval if it exists and hasn't expired (checks cache first, then Redis)."""
        # Check local cache first
        if session_id in self._pending_approvals_cache:
            state, created_at = self._pending_approvals_cache[session_id]
            age = (datetime.now(timezone.utc) - created_at).total_seconds()

            if age > self.PENDING_APPROVAL_TTL_SECONDS:
                # Expired, clean it up
                del self._pending_approvals_cache[session_id]
                await self._remove_pending_approval_from_redis(session_id)
                logger.info(f"Pending approval for session {session_id} expired")
                return None

            return state

        # Not in cache, try Redis (in case another instance added it)
        try:
            if redis_client is not None:
                key = f"{self.PENDING_APPROVAL_KEY_PREFIX}{session_id}"
                data = await redis_client.client.get(key)
                if data:
                    approval_data = json.loads(data)
                    created_at = datetime.fromisoformat(approval_data.get("created_at"))
                    age = (datetime.now(timezone.utc) - created_at).total_seconds()

                    if age <= self.PENDING_APPROVAL_TTL_SECONDS:
                        state = self._deserialize_state(approval_data.get("state"))
                        # Cache it locally
                        self._pending_approvals_cache[session_id] = (state, created_at)
                        return state
                    else:
                        # Expired, delete from Redis
                        await redis_client.client.delete(key)

        except Exception as e:
            logger.error(f"Error fetching pending approval from Redis: {e}")

        return None

    async def _remove_pending_approval(self, session_id: str):
        """Remove a pending approval from cache and Redis."""
        if session_id in self._pending_approvals_cache:
            del self._pending_approvals_cache[session_id]
        await self._remove_pending_approval_from_redis(session_id)

    # Synchronous wrapper for backwards compatibility
    def _add_pending_approval_sync(self, session_id: str, state: AgentState):
        """Synchronous wrapper - use _add_pending_approval for async contexts."""
        created_at = datetime.now(timezone.utc)
        self._pending_approvals_cache[session_id] = (state, created_at)
        # Note: Redis persistence happens in async context

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
                "timestamp": datetime.now(timezone.utc).isoformat(),
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

        state["timestamp"] = datetime.now(timezone.utc).isoformat()

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
                    "timestamp": datetime.now(timezone.utc).isoformat()
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

        RELIABILITY: State is persisted to Redis for crash recovery.
        """
        session_id = state["session_id"]

        logger.info(f"[WAIT] Session {session_id}: Waiting for approval")

        # Store state for later retrieval with TTL tracking and Redis persistence
        await self._add_pending_approval(session_id, state)

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
        LEARN: Schedule delayed reward measurement based on engagement delta.

        Instead of immediate reward calculation, this schedules a delayed measurement
        to capture the actual impact of the intervention on engagement.

        The reward will be calculated after REWARD_MEASUREMENT_DELAY_SECONDS by
        comparing pre-intervention and post-intervention engagement scores.
        """
        logger.info(f"[LEARN] Session {state['session_id']}: Scheduling reward measurement")

        state["status"] = AgentStatus.LEARNING

        # Store pre-intervention engagement for later comparison
        state["pre_intervention_engagement"] = state["engagement_score"]
        state["post_intervention_engagement"] = None  # Will be filled by delayed measurement

        if state["success"] and state.get("intervention_id"):
            # Schedule delayed reward measurement for successful interventions
            # The actual Thompson Sampling update happens after the delay
            self._schedule_reward_measurement(state)

            logger.info(
                f"[LEARN] Scheduled delayed reward measurement for intervention "
                f"{state['intervention_id'][:8]}... (delay: {self.REWARD_MEASUREMENT_DELAY_SECONDS}s)"
            )

            # Set provisional reward (will be updated by delayed measurement)
            state["reward"] = 0.5  # Provisional - actual reward determined later
        else:
            # Intervention failed to execute - immediate negative feedback
            state["reward"] = 0.0

            # Update Thompson Sampling immediately for failures
            if state.get("context") and state.get("selected_intervention"):
                self.thompson_sampling.update(
                    context=state["context"],
                    intervention_type=state["selected_intervention"],
                    success=False,
                    reward=0.0
                )

                logger.info(
                    f"[LEARN] Updated Thompson Sampling with failure: "
                    f"intervention={state['selected_intervention'].value}, reward=0.0"
                )

                # Persist Thompson Sampling stats
                try:
                    await self.thompson_sampling.save_to_redis()
                except Exception as e:
                    logger.error(f"[LEARN] Failed to persist Thompson Sampling stats: {e}")

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
            "pre_intervention_engagement": engagement_score,  # Store for delta calculation
            "post_intervention_engagement": None,  # Filled by delayed measurement
            "status": AgentStatus.IDLE,
            "timestamp": datetime.now(timezone.utc).isoformat(),
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
        state = await self._get_pending_approval(session_id)
        if state is None:
            raise ValueError(f"No pending approval for session {session_id} (may have expired)")

        state["approved"] = approved

        if approved:
            logger.info(f"[APPROVAL] Session {session_id}: Intervention approved")
            # Remove from pending before continuing
            await self._remove_pending_approval(session_id)
            # Continue workflow from wait_approval node
            config = {"configurable": {"thread_id": session_id}}
            final_state = await self.app.ainvoke(state, config)
            return final_state
        else:
            logger.info(f"[APPROVAL] Session {session_id}: Intervention dismissed")
            # Remove from pending
            await self._remove_pending_approval(session_id)
            return state

    async def get_pending_approval_async(self, session_id: str) -> Optional[AgentDecision]:
        """Get pending approval for a session (async version)."""
        state = await self._get_pending_approval(session_id)
        if state is None:
            return None

        return AgentDecision(
            intervention_type=state["selected_intervention"],
            confidence=state["confidence"],
            context=state["context"],
            reasoning=state["explanation"],
            requires_approval=state["requires_approval"],
            timestamp=datetime.fromisoformat(state["timestamp"])
        )

    def get_pending_approval(self, session_id: str) -> Optional[AgentDecision]:
        """Get pending approval for a session (sync version - uses cache only)."""
        if session_id not in self._pending_approvals_cache:
            return None

        state, created_at = self._pending_approvals_cache[session_id]
        age = (datetime.now(timezone.utc) - created_at).total_seconds()

        if age > self.PENDING_APPROVAL_TTL_SECONDS:
            return None

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
        old_mode = self._current_mode
        self._current_mode = mode
        logger.info(f"Agent mode changed from {old_mode.value} to {mode.value}")

    @property
    def current_mode(self) -> AgentMode:
        """Get the current agent mode."""
        return self._current_mode

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
