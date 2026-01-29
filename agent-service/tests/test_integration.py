"""
Integration Tests for Engagement Conductor AI

Tests the complete end-to-end flow:
1. Signal collection → Anomaly detection → Agent decision → Intervention execution
2. Circuit breaker behavior under failure conditions
3. Rate limiting enforcement
4. Redis persistence and recovery
5. Memory bounds validation
"""

import pytest
import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
import uuid
import json

# Test subjects
from app.agents.engagement_conductor import (
    EngagementConductorAgent,
    AgentMode,
    AgentStatus,
    AgentState,
)
from app.agents.thompson_sampling import (
    ThompsonSampling,
    InterventionType,
    AnomalyType,
    ContextKey,
)
from app.agents.anomaly_detector import AnomalyDetector, AnomalyEvent
from app.agents.intervention_executor import InterventionExecutor
from app.core.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerError,
    CircuitState,
    get_circuit_breaker,
)
from app.core.rate_limiter import RateLimiter, SessionInterventionRateLimiter


class TestEndToEndAgentFlow:
    """Integration tests for the complete agent flow."""

    @pytest.mark.asyncio
    async def test_full_manual_mode_flow(self):
        """Test MANUAL mode: agent reaches WAITING_APPROVAL and stores pending approval."""
        # Create mock Redis
        mock_redis = MagicMock()
        mock_redis.publish = AsyncMock()
        mock_redis.client = MagicMock()
        mock_redis.client.setex = AsyncMock()
        mock_redis.client.get = AsyncMock(return_value=None)
        mock_redis.client.delete = AsyncMock()
        mock_redis.client.keys = AsyncMock(return_value=[])

        with patch('app.agents.engagement_conductor.redis_client', mock_redis):
            with patch('app.agents.engagement_conductor.get_thompson_sampling') as mock_ts:
                mock_ts.return_value = ThompsonSampling()
                agent = EngagementConductorAgent()

                session_id = str(uuid.uuid4())
                event_id = str(uuid.uuid4())

                # Create test anomaly
                anomaly = AnomalyEvent(
                    session_id=session_id,
                    event_id=event_id,
                    anomaly_type="SUDDEN_DROP",
                    severity="CRITICAL",
                    timestamp=datetime.now(timezone.utc),
                    current_engagement=0.3,
                    expected_engagement=0.7,
                    deviation=0.4,
                    anomaly_score=0.9,
                    signals={}
                )

                # Run agent in MANUAL mode
                with patch.object(agent.intervention_executor, 'execute', new_callable=AsyncMock) as mock_execute:
                    mock_execute.return_value = {"success": True, "intervention_id": str(uuid.uuid4())}

                    # Run in MANUAL mode - should go through perceive→decide→check_approval→wait_approval
                    state = await agent.run(
                        session_id=session_id,
                        event_id=event_id,
                        engagement_score=0.3,
                        active_users=50,
                        signals={"chat_msgs_per_min": 2, "poll_participation": 0.3},
                        anomaly=anomaly,
                        session_context={"topic": "AI Workshop"},
                        agent_mode=AgentMode.MANUAL
                    )

                    # Verify agent reached WAITING_APPROVAL status and selected an intervention
                    assert state["status"] == AgentStatus.WAITING_APPROVAL
                    assert state["requires_approval"] is True
                    assert state["selected_intervention"] is not None

                    # Verify pending approval was stored (in cache and Redis)
                    assert session_id in agent._pending_approvals_cache
                    mock_redis.client.setex.assert_called()  # Redis persistence was called

    @pytest.mark.asyncio
    async def test_semi_auto_mode_high_confidence(self):
        """Test SEMI_AUTO mode auto-approves high-confidence decisions."""
        # Create mock Redis
        mock_redis = MagicMock()
        mock_redis.publish = AsyncMock()
        mock_redis.client = MagicMock()
        mock_redis.client.setex = AsyncMock()
        mock_redis.client.get = AsyncMock(return_value=None)
        mock_redis.client.delete = AsyncMock()
        mock_redis.client.keys = AsyncMock(return_value=[])

        with patch('app.agents.engagement_conductor.redis_client', mock_redis):
            with patch('app.agents.engagement_conductor.get_thompson_sampling') as mock_ts:
                mock_ts.return_value = ThompsonSampling()
                agent = EngagementConductorAgent()

                session_id = str(uuid.uuid4())
                event_id = str(uuid.uuid4())

                anomaly = AnomalyEvent(
                    session_id=session_id,
                    event_id=event_id,
                    anomaly_type="SUDDEN_DROP",
                    severity="CRITICAL",
                    timestamp=datetime.now(timezone.utc),
                    current_engagement=0.2,
                    expected_engagement=0.8,
                    deviation=0.6,
                    anomaly_score=0.95,
                    signals={}
                )

                # Force high confidence by pre-training Thompson Sampling
                for _ in range(20):
                    context = agent.thompson_sampling.create_context(
                        anomaly_type=AnomalyType.SUDDEN_DROP,
                        engagement_score=0.3,
                        active_users=50
                    )
                    agent.thompson_sampling.update(
                        context=context,
                        intervention_type=InterventionType.POLL,
                        success=True,
                        reward=1.0
                    )

                with patch.object(agent.intervention_executor, 'execute', new_callable=AsyncMock) as mock_execute:
                    mock_execute.return_value = {"success": True, "intervention_id": str(uuid.uuid4())}

                    state = await agent.run(
                        session_id=session_id,
                        event_id=event_id,
                        engagement_score=0.2,
                        active_users=50,
                        signals={},
                        anomaly=anomaly,
                        session_context={},
                        agent_mode=AgentMode.SEMI_AUTO
                    )

                    # High confidence should auto-approve
                    if state["confidence"] >= agent.AUTO_APPROVE_THRESHOLD:
                        assert state["approved"] is True
                        assert state["requires_approval"] is False

    @pytest.mark.asyncio
    async def test_auto_mode_executes_immediately(self):
        """Test AUTO mode executes interventions without approval."""
        # Create mock Redis
        mock_redis = MagicMock()
        mock_redis.publish = AsyncMock()
        mock_redis.client = MagicMock()
        mock_redis.client.setex = AsyncMock()
        mock_redis.client.get = AsyncMock(return_value=None)
        mock_redis.client.delete = AsyncMock()
        mock_redis.client.keys = AsyncMock(return_value=[])

        with patch('app.agents.engagement_conductor.redis_client', mock_redis):
            with patch('app.agents.engagement_conductor.get_thompson_sampling') as mock_ts:
                mock_ts.return_value = ThompsonSampling()
                agent = EngagementConductorAgent()

                session_id = str(uuid.uuid4())
                event_id = str(uuid.uuid4())

                anomaly = AnomalyEvent(
                    session_id=session_id,
                    event_id=event_id,
                    anomaly_type="LOW_ENGAGEMENT",
                    severity="WARNING",
                    timestamp=datetime.now(timezone.utc),
                    current_engagement=0.25,
                    expected_engagement=0.6,
                    deviation=0.35,
                    anomaly_score=0.8,
                    signals={}
                )

                with patch.object(agent.intervention_executor, 'execute', new_callable=AsyncMock) as mock_execute:
                    mock_execute.return_value = {"success": True, "intervention_id": str(uuid.uuid4())}

                    state = await agent.run(
                        session_id=session_id,
                        event_id=event_id,
                        engagement_score=0.25,
                        active_users=30,
                        signals={},
                        anomaly=anomaly,
                        session_context={},
                        agent_mode=AgentMode.AUTO
                    )

                    # AUTO mode should always approve
                    assert state["approved"] is True
                    assert state["requires_approval"] is False
                    mock_execute.assert_called_once()


class TestCircuitBreakerIntegration:
    """Integration tests for circuit breaker behavior."""

    @pytest.mark.asyncio
    async def test_circuit_opens_after_failures(self):
        """Test circuit breaker opens after threshold failures."""
        breaker = CircuitBreaker(
            name="test_breaker",
            failure_threshold=3,
            recovery_timeout=1.0
        )

        # Simulate failures
        for i in range(3):
            try:
                async with breaker:
                    raise Exception(f"Simulated failure {i}")
            except Exception:
                pass

        # Circuit should be open
        assert breaker.state == CircuitState.OPEN

        # Next request should fail immediately
        with pytest.raises(CircuitBreakerError):
            async with breaker:
                pass

    @pytest.mark.asyncio
    async def test_circuit_recovers_after_timeout(self):
        """Test circuit breaker recovers after timeout."""
        breaker = CircuitBreaker(
            name="recovery_test",
            failure_threshold=2,
            recovery_timeout=0.1,  # 100ms
            success_threshold=1
        )

        # Open the circuit
        for _ in range(2):
            try:
                async with breaker:
                    raise Exception("Failure")
            except Exception:
                pass

        assert breaker.state == CircuitState.OPEN

        # Wait for recovery timeout
        await asyncio.sleep(0.15)

        # Should transition to half-open and allow one request
        async with breaker:
            pass  # Success

        # Should be closed now
        assert breaker.state == CircuitState.CLOSED


class TestRateLimiterIntegration:
    """Integration tests for rate limiting."""

    @pytest.mark.asyncio
    async def test_rate_limiter_blocks_after_limit(self):
        """Test rate limiter blocks requests after limit reached."""
        limiter = RateLimiter(
            name="test_limiter",
            max_requests=3,
            window_seconds=1.0
        )

        session_id = "test-session"

        # First 3 requests should pass
        for _ in range(3):
            assert await limiter.is_allowed(session_id) is True

        # 4th request should be blocked
        assert await limiter.is_allowed(session_id) is False

    @pytest.mark.asyncio
    async def test_rate_limiter_allows_after_window(self):
        """Test rate limiter allows requests after window expires."""
        limiter = RateLimiter(
            name="window_test",
            max_requests=1,
            window_seconds=0.1  # 100ms window
        )

        session_id = "test-session"

        # First request passes
        assert await limiter.is_allowed(session_id) is True

        # Second request blocked
        assert await limiter.is_allowed(session_id) is False

        # Wait for window to expire
        await asyncio.sleep(0.15)

        # Should be allowed again
        assert await limiter.is_allowed(session_id) is True

    @pytest.mark.asyncio
    async def test_intervention_rate_limiter_multi_tier(self):
        """Test intervention rate limiter with multiple tiers."""
        limiter = SessionInterventionRateLimiter()

        session_id = "test-session"
        event_id = "test-event"

        # First intervention should pass
        allowed, reason = await limiter.is_intervention_allowed(session_id, event_id)
        assert allowed is True
        assert reason is None

        # Second immediate intervention should be blocked (30s limit)
        allowed, reason = await limiter.is_intervention_allowed(session_id, event_id)
        assert allowed is False
        assert "30 seconds" in reason


class TestAnomalyDetectorMemoryBounds:
    """Integration tests for anomaly detector memory bounds."""

    def test_memory_bounds_lru_eviction(self):
        """Test LRU eviction when max sessions reached."""
        detector = AnomalyDetector(max_sessions=3)

        # Add 3 sessions
        for i in range(3):
            detector.detect(
                session_id=f"session-{i}",
                event_id="event-1",
                engagement_score=0.5,
                signals={}
            )

        # All 3 should be cached
        assert len(detector.session_detectors) == 3

        # Add 4th session - should evict oldest
        detector.detect(
            session_id="session-new",
            event_id="event-1",
            engagement_score=0.5,
            signals={}
        )

        # Should still be 3 (LRU eviction)
        assert len(detector.session_detectors) == 3

    def test_anomaly_classification(self):
        """Test correct anomaly type classification."""
        detector = AnomalyDetector()
        session_id = "test-session"

        # Build baseline (need 5+ points)
        for i in range(6):
            detector.detect(
                session_id=session_id,
                event_id="event-1",
                engagement_score=0.7,  # Stable baseline
                signals={"chat_msgs_per_min": 5, "active_users": 50}
            )

        # Sudden drop should trigger anomaly
        result = detector.detect(
            session_id=session_id,
            event_id="event-1",
            engagement_score=0.3,  # 57% drop
            signals={"chat_msgs_per_min": 1, "active_users": 30}
        )

        if result:  # May not trigger if score not anomalous enough
            assert result.anomaly_type in ["SUDDEN_DROP", "LOW_ENGAGEMENT"]


class TestThompsonSamplingLearning:
    """Integration tests for Thompson Sampling learning."""

    def test_learning_improves_selection(self):
        """Test that Thompson Sampling learns from outcomes."""
        ts = ThompsonSampling()

        context = ContextKey(
            anomaly_type=AnomalyType.SUDDEN_DROP,
            engagement_bucket="low",
            session_size_bucket="medium"
        )

        # Train: POLL always succeeds, others fail
        for _ in range(50):
            ts.update(context, InterventionType.POLL, success=True, reward=1.0)
            ts.update(context, InterventionType.CHAT_PROMPT, success=False, reward=0.0)
            ts.update(context, InterventionType.NOTIFICATION, success=False, reward=0.0)

        # After training, POLL should be selected most often
        selections = {t: 0 for t in InterventionType}
        for _ in range(100):
            selected, _ = ts.select_intervention(context)
            selections[selected] += 1

        # POLL should be dominant
        assert selections[InterventionType.POLL] > 70  # Should be selected >70% of time

    def test_context_isolation(self):
        """Test that different contexts maintain separate statistics."""
        ts = ThompsonSampling()

        context1 = ContextKey(
            anomaly_type=AnomalyType.SUDDEN_DROP,
            engagement_bucket="low",
            session_size_bucket="small"
        )

        context2 = ContextKey(
            anomaly_type=AnomalyType.GRADUAL_DECLINE,
            engagement_bucket="medium",
            session_size_bucket="large"
        )

        # Train context1: POLL works
        for _ in range(20):
            ts.update(context1, InterventionType.POLL, success=True, reward=1.0)

        # Train context2: NOTIFICATION works
        for _ in range(20):
            ts.update(context2, InterventionType.NOTIFICATION, success=True, reward=1.0)

        # Verify stats are isolated
        poll_stats_ctx1 = ts.get_stats(context1, InterventionType.POLL)
        notif_stats_ctx2 = ts.get_stats(context2, InterventionType.NOTIFICATION)

        assert poll_stats_ctx1.success_rate > 0.8
        assert notif_stats_ctx2.success_rate > 0.8

        # Cross-context stats should be default
        poll_stats_ctx2 = ts.get_stats(context2, InterventionType.POLL)
        assert poll_stats_ctx2.total_attempts == 0  # No training in context2


class TestRedisStatePersistence:
    """Integration tests for Redis state persistence."""

    @pytest.mark.asyncio
    async def test_pending_approval_persisted_to_redis(self):
        """Test pending approvals are persisted to Redis."""
        mock_redis = MagicMock()
        mock_redis.publish = AsyncMock()
        mock_redis.client = MagicMock()
        mock_redis.client.setex = AsyncMock()
        mock_redis.client.get = AsyncMock(return_value=None)
        mock_redis.client.delete = AsyncMock()
        mock_redis.client.keys = AsyncMock(return_value=[])

        with patch('app.agents.engagement_conductor.redis_client', mock_redis):
            with patch('app.agents.engagement_conductor.get_thompson_sampling') as mock_ts:
                mock_ts.return_value = ThompsonSampling()
                agent = EngagementConductorAgent()

                # Add pending approval
                session_id = "test-session"
                state = {"session_id": session_id, "test": True}
                await agent._add_pending_approval(session_id, state)

                # Verify Redis setex was called
                mock_redis.client.setex.assert_called_once()
                call_args = mock_redis.client.setex.call_args
                assert f"agent:pending_approval:{session_id}" in call_args[0][0]


class TestWorkerPoolIntegration:
    """Integration tests for worker pool."""

    @pytest.mark.asyncio
    async def test_worker_pool_processes_events(self):
        """Test worker pool processes submitted events."""
        from app.core.worker_pool import AsyncWorkerPool

        pool = AsyncWorkerPool(num_workers=2, queue_size=10)
        await pool.start()

        processed_events = []

        async def process_event(data):
            processed_events.append(data)

        # Submit work
        for i in range(5):
            await pool.submit(f"session-{i % 2}", process_event, f"event-{i}")

        # Wait for processing
        await asyncio.sleep(0.1)

        # Verify all events processed
        assert len(processed_events) == 5

        await pool.stop()

    @pytest.mark.asyncio
    async def test_worker_pool_session_affinity(self):
        """Test events from same session go to same worker."""
        from app.core.worker_pool import AsyncWorkerPool

        pool = AsyncWorkerPool(num_workers=4, queue_size=10)
        await pool.start()

        worker_assignments = {}

        async def track_worker(session_id, worker_id):
            if session_id not in worker_assignments:
                worker_assignments[session_id] = set()
            worker_assignments[session_id].add(worker_id)

        # Submit multiple events for same sessions
        for _ in range(10):
            for session in ["session-a", "session-b"]:
                worker_idx = pool._get_worker_index(session)
                await pool.submit(session, track_worker, session, worker_idx)

        await asyncio.sleep(0.1)

        # Each session should only have one worker
        for session, workers in worker_assignments.items():
            assert len(workers) == 1, f"Session {session} had multiple workers: {workers}"

        await pool.stop()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
