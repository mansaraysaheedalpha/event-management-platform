"""
Unit tests for Engagement Conductor Agent
"""
import pytest
import asyncio
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
import uuid

from app.agents.engagement_conductor import (
    EngagementConductorAgent,
    AgentMode,
    AgentStatus,
    AgentState,
    AgentDecision,
)
from app.agents.thompson_sampling import InterventionType, AnomalyType, ContextKey


class TestAgentInitialization:
    """Tests for EngagementConductorAgent initialization"""

    def test_init_creates_workflow(self):
        """Test that initialization creates LangGraph workflow"""
        with patch('app.agents.engagement_conductor.get_thompson_sampling') as mock_ts:
            mock_ts.return_value = MagicMock()
            agent = EngagementConductorAgent()

            assert agent.workflow is not None
            assert agent.app is not None
            assert agent.memory is not None

    def test_init_sets_default_mode(self):
        """Test that default mode is MANUAL"""
        with patch('app.agents.engagement_conductor.get_thompson_sampling') as mock_ts:
            mock_ts.return_value = MagicMock()
            agent = EngagementConductorAgent()

            assert agent.current_mode == AgentMode.MANUAL

    def test_init_empty_pending_approvals(self):
        """Test that pending approvals starts empty"""
        with patch('app.agents.engagement_conductor.get_thompson_sampling') as mock_ts:
            mock_ts.return_value = MagicMock()
            agent = EngagementConductorAgent()

            assert len(agent.pending_approvals) == 0


class TestAgentMode:
    """Tests for agent mode management"""

    @pytest.mark.asyncio
    async def test_set_mode_updates_current_mode(self):
        """Test that set_mode updates the current mode"""
        with patch('app.agents.engagement_conductor.get_thompson_sampling') as mock_ts:
            mock_ts.return_value = MagicMock()
            agent = EngagementConductorAgent()

            await agent.set_mode(AgentMode.AUTO)
            assert agent.current_mode == AgentMode.AUTO

            await agent.set_mode(AgentMode.SEMI_AUTO)
            assert agent.current_mode == AgentMode.SEMI_AUTO

            await agent.set_mode(AgentMode.MANUAL)
            assert agent.current_mode == AgentMode.MANUAL

    def test_current_mode_property(self):
        """Test current_mode property returns correct value"""
        with patch('app.agents.engagement_conductor.get_thompson_sampling') as mock_ts:
            mock_ts.return_value = MagicMock()
            agent = EngagementConductorAgent()

            agent._current_mode = AgentMode.SEMI_AUTO
            assert agent.current_mode == AgentMode.SEMI_AUTO


class TestPendingApprovals:
    """Tests for pending approvals management with TTL"""

    def test_add_pending_approval(self):
        """Test adding a pending approval"""
        with patch('app.agents.engagement_conductor.get_thompson_sampling') as mock_ts:
            mock_ts.return_value = MagicMock()
            agent = EngagementConductorAgent()

            session_id = "test-session-123"
            state = {"session_id": session_id, "status": AgentStatus.WAITING_APPROVAL}

            agent._add_pending_approval(session_id, state)

            assert session_id in agent._pending_approvals
            stored_state, timestamp = agent._pending_approvals[session_id]
            assert stored_state == state
            assert isinstance(timestamp, datetime)

    def test_get_pending_approval_valid(self):
        """Test getting a valid pending approval"""
        with patch('app.agents.engagement_conductor.get_thompson_sampling') as mock_ts:
            mock_ts.return_value = MagicMock()
            agent = EngagementConductorAgent()

            session_id = "test-session-456"
            state = {"session_id": session_id, "confidence": 0.8}

            agent._add_pending_approval(session_id, state)
            result = agent._get_pending_approval(session_id)

            assert result == state

    def test_get_pending_approval_expired(self):
        """Test that expired approvals return None"""
        with patch('app.agents.engagement_conductor.get_thompson_sampling') as mock_ts:
            mock_ts.return_value = MagicMock()
            agent = EngagementConductorAgent()

            session_id = "test-session-789"
            state = {"session_id": session_id}

            # Manually add with old timestamp
            old_time = datetime.now(timezone.utc) - timedelta(seconds=agent.PENDING_APPROVAL_TTL_SECONDS + 100)
            agent._pending_approvals[session_id] = (state, old_time)

            result = agent._get_pending_approval(session_id)

            assert result is None
            assert session_id not in agent._pending_approvals

    def test_get_pending_approval_not_found(self):
        """Test getting non-existent approval returns None"""
        with patch('app.agents.engagement_conductor.get_thompson_sampling') as mock_ts:
            mock_ts.return_value = MagicMock()
            agent = EngagementConductorAgent()

            result = agent._get_pending_approval("non-existent")
            assert result is None

    def test_remove_pending_approval(self):
        """Test removing a pending approval"""
        with patch('app.agents.engagement_conductor.get_thompson_sampling') as mock_ts:
            mock_ts.return_value = MagicMock()
            agent = EngagementConductorAgent()

            session_id = "test-session-remove"
            agent._add_pending_approval(session_id, {"test": True})

            agent._remove_pending_approval(session_id)

            assert session_id not in agent._pending_approvals

    def test_max_pending_approvals_limit(self):
        """Test that max pending approvals limit is enforced"""
        with patch('app.agents.engagement_conductor.get_thompson_sampling') as mock_ts:
            mock_ts.return_value = MagicMock()
            agent = EngagementConductorAgent()

            # Set a low limit for testing
            original_limit = agent.MAX_PENDING_APPROVALS
            agent.MAX_PENDING_APPROVALS = 3

            try:
                # Add more than limit
                for i in range(5):
                    agent._add_pending_approval(f"session-{i}", {"index": i})

                # Should only have MAX_PENDING_APPROVALS entries
                assert len(agent._pending_approvals) == 3

                # Should have the most recent ones
                assert "session-4" in agent._pending_approvals
                assert "session-3" in agent._pending_approvals
                assert "session-2" in agent._pending_approvals

            finally:
                agent.MAX_PENDING_APPROVALS = original_limit

    def test_pending_approvals_backwards_compatible_property(self):
        """Test that pending_approvals property returns dict without timestamps"""
        with patch('app.agents.engagement_conductor.get_thompson_sampling') as mock_ts:
            mock_ts.return_value = MagicMock()
            agent = EngagementConductorAgent()

            session_id = "test-compat"
            state = {"session_id": session_id, "value": 123}
            agent._add_pending_approval(session_id, state)

            # Property should return just the state, not the tuple
            result = agent.pending_approvals
            assert result[session_id] == state


class TestCleanupTask:
    """Tests for cleanup task functionality"""

    @pytest.mark.asyncio
    async def test_start_cleanup_task(self):
        """Test starting the cleanup task"""
        with patch('app.agents.engagement_conductor.get_thompson_sampling') as mock_ts:
            mock_ts.return_value = MagicMock()
            agent = EngagementConductorAgent()

            await agent.start_cleanup_task()

            assert agent._cleanup_task is not None
            assert not agent._cleanup_task.done()

            # Clean up
            await agent.stop_cleanup_task()

    @pytest.mark.asyncio
    async def test_stop_cleanup_task(self):
        """Test stopping the cleanup task"""
        with patch('app.agents.engagement_conductor.get_thompson_sampling') as mock_ts:
            mock_ts.return_value = MagicMock()
            agent = EngagementConductorAgent()

            await agent.start_cleanup_task()
            await agent.stop_cleanup_task()

            assert agent._cleanup_task.done() or agent._cleanup_task.cancelled()


class TestApproveIntervention:
    """Tests for intervention approval"""

    @pytest.mark.asyncio
    async def test_approve_intervention_not_found(self):
        """Test approving non-existent intervention raises error"""
        with patch('app.agents.engagement_conductor.get_thompson_sampling') as mock_ts:
            mock_ts.return_value = MagicMock()
            agent = EngagementConductorAgent()

            with pytest.raises(ValueError, match="No pending approval"):
                await agent.approve_intervention("non-existent", approved=True)

    @pytest.mark.asyncio
    async def test_approve_intervention_dismiss(self):
        """Test dismissing an intervention"""
        with patch('app.agents.engagement_conductor.get_thompson_sampling') as mock_ts:
            mock_ts.return_value = MagicMock()
            agent = EngagementConductorAgent()

            session_id = "test-dismiss"
            state = {
                "session_id": session_id,
                "approved": False,
                "selected_intervention": InterventionType.POLL,
                "confidence": 0.7
            }
            agent._add_pending_approval(session_id, state)

            result = await agent.approve_intervention(session_id, approved=False)

            assert result["approved"] is False
            assert session_id not in agent._pending_approvals


class TestGetState:
    """Tests for get_state method"""

    @pytest.mark.asyncio
    async def test_get_state_no_pending(self):
        """Test get_state with no pending approvals"""
        with patch('app.agents.engagement_conductor.get_thompson_sampling') as mock_ts:
            mock_ts.return_value = MagicMock()
            agent = EngagementConductorAgent()

            state = await agent.get_state()

            assert state["mode"] == "MANUAL"
            assert state["status"] == "MONITORING"
            assert state["current_decision"] is None


class TestAutoApproveThreshold:
    """Tests for auto-approve threshold"""

    def test_auto_approve_threshold_value(self):
        """Test that auto-approve threshold is set correctly"""
        with patch('app.agents.engagement_conductor.get_thompson_sampling') as mock_ts:
            mock_ts.return_value = MagicMock()
            agent = EngagementConductorAgent()

            # Default threshold should be 0.75
            assert agent.AUTO_APPROVE_THRESHOLD == 0.75

    def test_ttl_values(self):
        """Test TTL configuration values"""
        with patch('app.agents.engagement_conductor.get_thompson_sampling') as mock_ts:
            mock_ts.return_value = MagicMock()
            agent = EngagementConductorAgent()

            # TTL should be 30 minutes (1800 seconds)
            assert agent.PENDING_APPROVAL_TTL_SECONDS == 1800

            # Max pending approvals should be 1000
            assert agent.MAX_PENDING_APPROVALS == 1000


class TestAgentDecision:
    """Tests for AgentDecision dataclass"""

    def test_agent_decision_creation(self):
        """Test creating an AgentDecision"""
        context = ContextKey(
            anomaly_type=AnomalyType.SUDDEN_DROP,
            engagement_bucket='low',
            session_size_bucket='medium'
        )

        decision = AgentDecision(
            intervention_type=InterventionType.POLL,
            confidence=0.85,
            context=context,
            reasoning="Engagement dropped significantly",
            requires_approval=True,
            timestamp=datetime.now(timezone.utc)
        )

        assert decision.intervention_type == InterventionType.POLL
        assert decision.confidence == 0.85
        assert decision.requires_approval is True


class TestGetPendingApprovalDecision:
    """Tests for get_pending_approval method"""

    def test_get_pending_approval_returns_decision(self):
        """Test get_pending_approval returns AgentDecision"""
        with patch('app.agents.engagement_conductor.get_thompson_sampling') as mock_ts:
            mock_ts.return_value = MagicMock()
            agent = EngagementConductorAgent()

            session_id = "test-decision"
            context = ContextKey(
                anomaly_type=AnomalyType.GRADUAL_DECLINE,
                engagement_bucket='critical',
                session_size_bucket='small'
            )
            state = {
                "session_id": session_id,
                "selected_intervention": InterventionType.CHAT_PROMPT,
                "confidence": 0.72,
                "context": context,
                "explanation": "Gradual decline detected",
                "requires_approval": True,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            agent._add_pending_approval(session_id, state)

            decision = agent.get_pending_approval(session_id)

            assert decision is not None
            assert decision.intervention_type == InterventionType.CHAT_PROMPT
            assert decision.confidence == 0.72
            assert decision.requires_approval is True

    def test_get_pending_approval_returns_none_when_not_found(self):
        """Test get_pending_approval returns None when not found"""
        with patch('app.agents.engagement_conductor.get_thompson_sampling') as mock_ts:
            mock_ts.return_value = MagicMock()
            agent = EngagementConductorAgent()

            decision = agent.get_pending_approval("non-existent")
            assert decision is None
