"""Agent orchestration module"""

from app.orchestrator.agent_manager import (
    AgentOrchestrator,
    SessionAgentConfig,
    AgentMetrics,
    get_agent_orchestrator
)

# Global agent manager instance for API access
agent_manager = get_agent_orchestrator()

__all__ = [
    "AgentOrchestrator",
    "SessionAgentConfig",
    "AgentMetrics",
    "get_agent_orchestrator",
    "agent_manager",
]
