"""
Agent Orchestrator - Manages multiple engagement conductor agents

Handles:
- Running agents for multiple sessions simultaneously
- Agent lifecycle (start, stop, status)
- Agent mode configuration per session
- Collecting metrics across all agents
- Coordinating interventions across sessions
"""

import asyncio
from typing import Dict, List, Optional, Set
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import logging

from app.agents.engagement_conductor import (
    EngagementConductorAgent,
    AgentMode,
    AgentStatus,
    AgentState
)
from app.agents.thompson_sampling import get_thompson_sampling
from app.models.anomaly import Anomaly

logger = logging.getLogger(__name__)


@dataclass
class SessionAgentConfig:
    """Configuration for a session's agent"""
    session_id: str
    event_id: str
    agent_mode: AgentMode
    enabled: bool = True
    created_at: datetime = field(default_factory=datetime.utcnow)
    last_activity: datetime = field(default_factory=datetime.utcnow)


@dataclass
class AgentMetrics:
    """Metrics for an agent's performance"""
    session_id: str
    total_interventions: int = 0
    successful_interventions: int = 0
    failed_interventions: int = 0
    dismissed_interventions: int = 0
    auto_approved_interventions: int = 0
    manual_approved_interventions: int = 0
    average_confidence: float = 0.0
    average_response_time_ms: float = 0.0
    last_intervention_at: Optional[datetime] = None

    @property
    def success_rate(self) -> float:
        """Calculate success rate"""
        total = self.successful_interventions + self.failed_interventions
        if total == 0:
            return 0.0
        return self.successful_interventions / total

    @property
    def approval_rate(self) -> float:
        """Calculate approval rate (approved / total suggested)"""
        total = (self.auto_approved_interventions +
                 self.manual_approved_interventions +
                 self.dismissed_interventions)
        if total == 0:
            return 0.0
        approved = self.auto_approved_interventions + self.manual_approved_interventions
        return approved / total


class AgentOrchestrator:
    """
    Orchestrates multiple engagement conductor agents across sessions.

    Features:
    - Manages agent lifecycle for multiple concurrent sessions
    - Configures agent mode per session
    - Collects and aggregates metrics
    - Handles intervention approvals
    - Provides global control and monitoring
    """

    def __init__(self):
        """Initialize agent orchestrator"""
        # Session configurations
        self.configs: Dict[str, SessionAgentConfig] = {}

        # Active agents (one per session)
        self.agents: Dict[str, EngagementConductorAgent] = {}

        # Running tasks
        self.tasks: Dict[str, asyncio.Task] = {}

        # Metrics
        self.metrics: Dict[str, AgentMetrics] = {}

        # Shared Thompson Sampling (learns across all sessions)
        self.thompson_sampling = get_thompson_sampling()

        logger.info("AgentOrchestrator initialized")

    # ==================== SESSION MANAGEMENT ====================

    def register_session(
        self,
        session_id: str,
        event_id: str,
        agent_mode: AgentMode = AgentMode.MANUAL
    ):
        """
        Register a session for agent monitoring.

        Args:
            session_id: Session ID
            event_id: Event ID
            agent_mode: Operating mode (MANUAL, SEMI_AUTO, AUTO)
        """
        if session_id in self.configs:
            logger.warning(f"Session {session_id} already registered, updating config")

        self.configs[session_id] = SessionAgentConfig(
            session_id=session_id,
            event_id=event_id,
            agent_mode=agent_mode
        )

        self.metrics[session_id] = AgentMetrics(session_id=session_id)

        logger.info(
            f"Registered session {session_id} with mode {agent_mode.value}"
        )

    async def create_agent(
        self,
        session_id: str,
        event_id: str,
        metadata: Optional[Dict] = None
    ) -> 'EngagementConductorAgent':
        """
        Create and initialize an agent for a session (async wrapper for API).

        Args:
            session_id: Session ID
            event_id: Event ID
            metadata: Optional session metadata

        Returns:
            Agent instance
        """
        # Register session
        self.register_session(session_id, event_id, AgentMode.MANUAL)

        # Create agent instance
        if session_id not in self.agents:
            self.agents[session_id] = EngagementConductorAgent(
                thompson_sampling=self.thompson_sampling
            )

        logger.info(f"Created agent for session {session_id}")
        return self.agents[session_id]

    def get_agent(self, session_id: str) -> Optional['EngagementConductorAgent']:
        """
        Get agent instance for a session.

        Args:
            session_id: Session ID

        Returns:
            Agent instance or None if not found
        """
        return self.agents.get(session_id)

    async def remove_agent(self, session_id: str):
        """
        Remove agent and unregister session (async wrapper for API).

        Args:
            session_id: Session ID
        """
        self.unregister_session(session_id)
        logger.info(f"Removed agent for session {session_id}")

    def unregister_session(self, session_id: str):
        """
        Unregister a session and stop its agent.

        Args:
            session_id: Session ID
        """
        if session_id not in self.configs:
            logger.warning(f"Session {session_id} not registered")
            return

        # Stop agent if running
        if session_id in self.tasks:
            self.tasks[session_id].cancel()
            del self.tasks[session_id]

        # Clean up
        del self.configs[session_id]
        if session_id in self.agents:
            del self.agents[session_id]

        # Keep metrics for historical analysis
        logger.info(f"Unregistered session {session_id}")

    def set_agent_mode(self, session_id: str, agent_mode: AgentMode):
        """
        Change agent mode for a session.

        Args:
            session_id: Session ID
            agent_mode: New agent mode
        """
        if session_id not in self.configs:
            raise ValueError(f"Session {session_id} not registered")

        old_mode = self.configs[session_id].agent_mode
        self.configs[session_id].agent_mode = agent_mode

        logger.info(
            f"Changed agent mode for session {session_id}: "
            f"{old_mode.value} → {agent_mode.value}"
        )

    def enable_agent(self, session_id: str):
        """Enable agent for a session"""
        if session_id not in self.configs:
            raise ValueError(f"Session {session_id} not registered")

        self.configs[session_id].enabled = True
        logger.info(f"Enabled agent for session {session_id}")

    def disable_agent(self, session_id: str):
        """Disable agent for a session"""
        if session_id not in self.configs:
            raise ValueError(f"Session {session_id} not registered")

        self.configs[session_id].enabled = False
        logger.info(f"Disabled agent for session {session_id}")

    # ==================== AGENT EXECUTION ====================

    async def run_agent(
        self,
        session_id: str,
        engagement_score: float,
        active_users: int,
        signals: Dict,
        anomaly: Optional[Anomaly],
        session_context: Dict
    ) -> Optional[AgentState]:
        """
        Run agent for a session (one cycle).

        Args:
            session_id: Session ID
            engagement_score: Current engagement score
            active_users: Number of active users
            signals: Current signals
            anomaly: Detected anomaly (if any)
            session_context: Session metadata

        Returns:
            Final agent state after execution
        """
        if session_id not in self.configs:
            logger.warning(f"Session {session_id} not registered, skipping agent run")
            return None

        config = self.configs[session_id]

        if not config.enabled:
            logger.debug(f"Agent disabled for session {session_id}, skipping")
            return None

        # Update last activity
        config.last_activity = datetime.utcnow()

        # Get or create agent for this session
        if session_id not in self.agents:
            self.agents[session_id] = EngagementConductorAgent(
                thompson_sampling=self.thompson_sampling
            )

        agent = self.agents[session_id]

        # Run agent
        start_time = datetime.utcnow()
        try:
            final_state = await agent.run(
                session_id=session_id,
                event_id=config.event_id,
                engagement_score=engagement_score,
                active_users=active_users,
                signals=signals,
                anomaly=anomaly,
                session_context=session_context,
                agent_mode=config.agent_mode
            )

            # Update metrics
            await self._update_metrics(session_id, final_state, start_time)

            return final_state

        except Exception as e:
            logger.error(f"Agent run failed for session {session_id}: {e}", exc_info=True)
            return None

    async def approve_intervention(
        self,
        session_id: str,
        approved: bool
    ) -> Optional[AgentState]:
        """
        Approve or dismiss a pending intervention.

        Args:
            session_id: Session ID
            approved: True to approve, False to dismiss

        Returns:
            Final agent state after approval
        """
        if session_id not in self.agents:
            raise ValueError(f"No agent running for session {session_id}")

        agent = self.agents[session_id]
        final_state = await agent.approve_intervention(session_id, approved)

        # Update metrics
        if approved:
            self.metrics[session_id].manual_approved_interventions += 1
        else:
            self.metrics[session_id].dismissed_interventions += 1

        return final_state

    # ==================== MONITORING & METRICS ====================

    async def _update_metrics(
        self,
        session_id: str,
        state: AgentState,
        start_time: datetime
    ):
        """Update metrics based on agent run"""
        if session_id not in self.metrics:
            return

        metrics = self.metrics[session_id]

        # Count interventions
        if state.get("selected_intervention"):
            metrics.total_interventions += 1
            metrics.last_intervention_at = datetime.utcnow()

            # Track approval method
            if state.get("requires_approval") and state.get("approved"):
                metrics.manual_approved_interventions += 1
            elif not state.get("requires_approval") and state.get("approved"):
                metrics.auto_approved_interventions += 1

            # Track outcomes
            if state.get("success"):
                metrics.successful_interventions += 1
            elif state.get("execution_result"):
                metrics.failed_interventions += 1

            # Update average confidence
            confidence = state.get("confidence", 0.0)
            total = metrics.total_interventions
            metrics.average_confidence = (
                (metrics.average_confidence * (total - 1) + confidence) / total
            )

        # Update response time
        response_time = (datetime.utcnow() - start_time).total_seconds() * 1000
        total = metrics.total_interventions or 1
        metrics.average_response_time_ms = (
            (metrics.average_response_time_ms * (total - 1) + response_time) / total
        )

    def get_metrics(self, session_id: str) -> Optional[AgentMetrics]:
        """Get metrics for a session"""
        return self.metrics.get(session_id)

    def get_all_metrics(self) -> Dict[str, AgentMetrics]:
        """Get metrics for all sessions"""
        return self.metrics.copy()

    def get_active_sessions(self) -> List[str]:
        """Get list of active session IDs"""
        return [
            sid for sid, config in self.configs.items()
            if config.enabled
        ]

    def get_agent_status(self, session_id: str) -> Optional[Dict]:
        """Get current status of agent for a session"""
        if session_id not in self.configs:
            return None

        config = self.configs[session_id]
        metrics = self.metrics.get(session_id)
        agent = self.agents.get(session_id)

        # Check for pending approval
        pending_approval = None
        if agent:
            pending_approval = agent.get_pending_approval(session_id)

        return {
            "session_id": session_id,
            "event_id": config.event_id,
            "agent_mode": config.agent_mode.value,
            "enabled": config.enabled,
            "created_at": config.created_at.isoformat(),
            "last_activity": config.last_activity.isoformat(),
            "metrics": {
                "total_interventions": metrics.total_interventions if metrics else 0,
                "success_rate": metrics.success_rate if metrics else 0.0,
                "approval_rate": metrics.approval_rate if metrics else 0.0,
                "average_confidence": metrics.average_confidence if metrics else 0.0,
                "average_response_time_ms": metrics.average_response_time_ms if metrics else 0.0,
            },
            "has_pending_approval": pending_approval is not None,
            "pending_approval": {
                "intervention_type": pending_approval.intervention_type.value,
                "confidence": pending_approval.confidence,
                "reasoning": pending_approval.reasoning,
            } if pending_approval else None
        }

    def get_global_stats(self) -> Dict:
        """Get aggregated statistics across all sessions"""
        total_interventions = sum(m.total_interventions for m in self.metrics.values())
        total_successful = sum(m.successful_interventions for m in self.metrics.values())
        total_failed = sum(m.failed_interventions for m in self.metrics.values())

        active_sessions = len(self.get_active_sessions())
        total_sessions = len(self.configs)

        return {
            "total_sessions": total_sessions,
            "active_sessions": active_sessions,
            "total_interventions": total_interventions,
            "successful_interventions": total_successful,
            "failed_interventions": total_failed,
            "global_success_rate": (
                total_successful / (total_successful + total_failed)
                if (total_successful + total_failed) > 0 else 0.0
            ),
            "thompson_sampling_contexts": len(self.thompson_sampling.stats),
        }

    # ==================== BULK OPERATIONS ====================

    def set_all_modes(self, agent_mode: AgentMode):
        """Set agent mode for all registered sessions"""
        for session_id in self.configs:
            self.set_agent_mode(session_id, agent_mode)
        logger.info(f"Set all sessions to mode: {agent_mode.value}")

    def enable_all(self):
        """Enable agents for all sessions"""
        for session_id in self.configs:
            self.enable_agent(session_id)
        logger.info("Enabled all agents")

    def disable_all(self):
        """Disable agents for all sessions"""
        for session_id in self.configs:
            self.disable_agent(session_id)
        logger.info("Disabled all agents")

    # ==================== PERSISTENCE ====================

    def export_state(self) -> Dict:
        """Export orchestrator state for persistence"""
        return {
            "configs": {
                sid: {
                    "session_id": config.session_id,
                    "event_id": config.event_id,
                    "agent_mode": config.agent_mode.value,
                    "enabled": config.enabled,
                    "created_at": config.created_at.isoformat(),
                    "last_activity": config.last_activity.isoformat(),
                }
                for sid, config in self.configs.items()
            },
            "metrics": {
                sid: {
                    "total_interventions": m.total_interventions,
                    "successful_interventions": m.successful_interventions,
                    "failed_interventions": m.failed_interventions,
                    "dismissed_interventions": m.dismissed_interventions,
                    "auto_approved_interventions": m.auto_approved_interventions,
                    "manual_approved_interventions": m.manual_approved_interventions,
                    "average_confidence": m.average_confidence,
                    "average_response_time_ms": m.average_response_time_ms,
                    "last_intervention_at": (
                        m.last_intervention_at.isoformat()
                        if m.last_intervention_at else None
                    ),
                }
                for sid, m in self.metrics.items()
            },
            "thompson_sampling": self.thompson_sampling.export_stats()
        }

    def import_state(self, state: Dict):
        """Import orchestrator state from persistence"""
        # Import configs
        for sid, config_data in state.get("configs", {}).items():
            self.configs[sid] = SessionAgentConfig(
                session_id=config_data["session_id"],
                event_id=config_data["event_id"],
                agent_mode=AgentMode(config_data["agent_mode"]),
                enabled=config_data["enabled"],
                created_at=datetime.fromisoformat(config_data["created_at"]),
                last_activity=datetime.fromisoformat(config_data["last_activity"]),
            )

        # Import metrics
        for sid, metrics_data in state.get("metrics", {}).items():
            self.metrics[sid] = AgentMetrics(
                session_id=sid,
                total_interventions=metrics_data["total_interventions"],
                successful_interventions=metrics_data["successful_interventions"],
                failed_interventions=metrics_data["failed_interventions"],
                dismissed_interventions=metrics_data["dismissed_interventions"],
                auto_approved_interventions=metrics_data["auto_approved_interventions"],
                manual_approved_interventions=metrics_data["manual_approved_interventions"],
                average_confidence=metrics_data["average_confidence"],
                average_response_time_ms=metrics_data["average_response_time_ms"],
                last_intervention_at=(
                    datetime.fromisoformat(metrics_data["last_intervention_at"])
                    if metrics_data.get("last_intervention_at") else None
                ),
            )

        # Import Thompson Sampling state
        if "thompson_sampling" in state:
            self.thompson_sampling.import_stats(state["thompson_sampling"])

        logger.info(f"Imported orchestrator state: {len(self.configs)} sessions")

    # ==================== GRACEFUL SHUTDOWN ====================

    async def shutdown(self):
        """
        Gracefully shutdown all agents and save state.

        Call this on application shutdown to:
        - Cancel all running tasks
        - Stop cleanup tasks
        - Save Thompson Sampling state
        - Export orchestrator state
        """
        logger.info("Initiating graceful shutdown of AgentOrchestrator...")

        # Cancel all running tasks
        cancelled_tasks = []
        for session_id, task in list(self.tasks.items()):
            if not task.done():
                task.cancel()
                cancelled_tasks.append(task)
                logger.info(f"Cancelled task for session {session_id}")

        # Wait for all tasks to complete cancellation
        if cancelled_tasks:
            await asyncio.gather(*cancelled_tasks, return_exceptions=True)
            logger.info(f"Cancelled {len(cancelled_tasks)} running tasks")

        # Stop cleanup tasks for all agents
        for session_id, agent in self.agents.items():
            try:
                await agent.stop_cleanup_task()
                logger.info(f"Stopped cleanup task for session {session_id}")
            except Exception as e:
                logger.error(f"Error stopping cleanup task for session {session_id}: {e}")

        # Save Thompson Sampling state to Redis
        try:
            await self.thompson_sampling.save_to_redis()
            logger.info("Saved Thompson Sampling state to Redis")
        except Exception as e:
            logger.error(f"Failed to save Thompson Sampling state: {e}")

        # Export state (could be saved to database)
        try:
            state = self.export_state()
            logger.info(f"Exported orchestrator state: {len(state.get('configs', {}))} sessions")
        except Exception as e:
            logger.error(f"Failed to export orchestrator state: {e}")

        # Clear all data structures
        self.tasks.clear()
        self.agents.clear()
        self.configs.clear()

        logger.info("AgentOrchestrator shutdown complete")


# Global orchestrator instance
_orchestrator_instance: Optional[AgentOrchestrator] = None


def get_agent_orchestrator() -> AgentOrchestrator:
    """Get or create global orchestrator instance"""
    global _orchestrator_instance
    if _orchestrator_instance is None:
        _orchestrator_instance = AgentOrchestrator()
    return _orchestrator_instance
