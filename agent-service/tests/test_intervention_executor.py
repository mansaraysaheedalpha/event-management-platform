"""
Unit tests for Intervention Executor
"""
import pytest
import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
import uuid

from app.agents.intervention_executor import InterventionExecutor, LLM_TIMEOUT_SECONDS
from app.agents.intervention_selector import InterventionRecommendation


class TestInterventionExecutorInit:
    """Tests for InterventionExecutor initialization"""

    def test_init_without_redis_client(self):
        """Test initialization without redis client uses lazy loading"""
        executor = InterventionExecutor()
        assert executor._redis is None
        assert executor.pending_interventions == {}

    def test_init_with_redis_client(self):
        """Test initialization with explicit redis client"""
        mock_redis = MagicMock()
        executor = InterventionExecutor(redis_client=mock_redis)
        assert executor._redis is mock_redis

    def test_redis_property_with_provided_client(self):
        """Test redis property returns provided client"""
        mock_redis = MagicMock()
        executor = InterventionExecutor(redis_client=mock_redis)
        assert executor.redis is mock_redis

    def test_redis_property_lazy_loading(self):
        """Test redis property lazy loads global client"""
        executor = InterventionExecutor()
        mock_global = MagicMock()

        with patch('app.core.redis_client.redis_client', mock_global):
            result = executor.redis
            assert result is mock_global

    def test_redis_property_raises_when_none(self):
        """Test redis property raises RuntimeError when global is None"""
        executor = InterventionExecutor()

        with patch('app.core.redis_client.redis_client', None):
            with pytest.raises(RuntimeError, match="Redis client not initialized"):
                _ = executor.redis


class TestInterventionRecommendation:
    """Tests for InterventionRecommendation creation"""

    def test_create_recommendation(self):
        """Test creating a valid recommendation"""
        rec = InterventionRecommendation(
            intervention_type='POLL',
            priority='HIGH',
            confidence=0.85,
            reason='Low engagement detected',
            context={
                'session_id': str(uuid.uuid4()),
                'event_id': str(uuid.uuid4()),
                'anomaly_type': 'SUDDEN_DROP'
            },
            estimated_impact=0.15
        )
        assert rec.intervention_type == 'POLL'
        assert rec.confidence == 0.85


@pytest.mark.asyncio
class TestExecuteIntervention:
    """Tests for execute method"""

    async def test_execute_routes_to_correct_handler(self):
        """Test that execute routes to correct intervention type handler"""
        mock_redis = MagicMock()
        mock_redis.publish = AsyncMock()
        executor = InterventionExecutor(redis_client=mock_redis)

        # Test each intervention type
        types = ['POLL', 'CHAT_PROMPT', 'NOTIFICATION', 'GAMIFICATION']

        for int_type in types:
            rec = InterventionRecommendation(
                intervention_type=int_type,
                priority='HIGH',
                confidence=0.8,
                reason='Test',
                context={
                    'session_id': str(uuid.uuid4()),
                    'event_id': str(uuid.uuid4()),
                },
                estimated_impact=0.1
            )

            with patch.object(executor, f'_execute_{int_type.lower()}', new_callable=AsyncMock) as mock_handler:
                mock_handler.return_value = {'success': True, 'intervention_id': 'test'}

                mock_db = AsyncMock()
                result = await executor.execute(rec, mock_db)

                mock_handler.assert_called_once()

    async def test_execute_returns_error_for_unknown_type(self):
        """Test execute returns error for unknown intervention type"""
        executor = InterventionExecutor(redis_client=MagicMock())

        rec = InterventionRecommendation(
            intervention_type='UNKNOWN_TYPE',
            priority='HIGH',
            confidence=0.8,
            reason='Test',
            context={
                'session_id': str(uuid.uuid4()),
                'event_id': str(uuid.uuid4()),
            },
            estimated_impact=0.1
        )

        mock_db = AsyncMock()
        result = await executor.execute(rec, mock_db)

        assert result['success'] is False
        assert 'Unknown intervention type' in result['error']


@pytest.mark.asyncio
class TestExecutePoll:
    """Tests for poll intervention execution"""

    async def test_execute_poll_validates_uuid(self):
        """Test that invalid session_id is caught early"""
        executor = InterventionExecutor(redis_client=MagicMock())

        rec = InterventionRecommendation(
            intervention_type='POLL',
            priority='HIGH',
            confidence=0.8,
            reason='Test',
            context={
                'session_id': 'invalid-uuid',  # Invalid!
                'event_id': str(uuid.uuid4()),
            },
            estimated_impact=0.1
        )

        mock_db = AsyncMock()
        result = await executor._execute_poll(rec, mock_db)

        assert result['success'] is False
        assert 'Invalid session_id format' in result['error']

    async def test_execute_poll_with_llm_timeout(self):
        """Test that LLM timeout falls back to template"""
        mock_redis = MagicMock()
        mock_redis.publish = AsyncMock()
        executor = InterventionExecutor(redis_client=mock_redis)

        rec = InterventionRecommendation(
            intervention_type='POLL',
            priority='HIGH',
            confidence=0.8,
            reason='Test',
            context={
                'session_id': str(uuid.uuid4()),
                'event_id': str(uuid.uuid4()),
                'anomaly_type': 'SUDDEN_DROP'
            },
            estimated_impact=0.1
        )

        # Mock poll_strategy to simulate timeout then success
        with patch('app.agents.intervention_executor.poll_strategy') as mock_strategy:
            # First call times out
            async def slow_generate(*args, **kwargs):
                await asyncio.sleep(LLM_TIMEOUT_SECONDS + 1)

            mock_poll = MagicMock()
            mock_poll.question = "Test question?"
            mock_poll.options = ["A", "B", "C"]
            mock_poll.duration = 60
            mock_poll.poll_type = "single"

            # First call is slow (will timeout), second call returns immediately
            call_count = [0]

            async def generate_with_ai(*args, **kwargs):
                call_count[0] += 1
                if call_count[0] == 1 and kwargs.get('use_llm', True):
                    await asyncio.sleep(LLM_TIMEOUT_SECONDS + 1)
                return mock_poll

            mock_strategy.generate_with_ai = generate_with_ai

            mock_db = AsyncMock()
            mock_db.add = MagicMock()
            mock_db.commit = AsyncMock()

            # Use a shorter timeout for testing
            with patch('app.agents.intervention_executor.LLM_TIMEOUT_SECONDS', 0.1):
                result = await executor._execute_poll(rec, mock_db)

            # Should have called generate_with_ai twice (timeout + fallback)
            assert call_count[0] == 2

    async def test_execute_poll_success(self):
        """Test successful poll execution"""
        mock_redis = MagicMock()
        mock_redis.publish = AsyncMock()
        executor = InterventionExecutor(redis_client=mock_redis)

        session_id = str(uuid.uuid4())
        event_id = str(uuid.uuid4())

        rec = InterventionRecommendation(
            intervention_type='POLL',
            priority='HIGH',
            confidence=0.85,
            reason='Engagement drop detected',
            context={
                'session_id': session_id,
                'event_id': event_id,
                'anomaly_type': 'SUDDEN_DROP'
            },
            estimated_impact=0.15
        )

        mock_poll = MagicMock()
        mock_poll.question = "What topic interests you most?"
        mock_poll.options = ["AI/ML", "Web Dev", "DevOps", "Other"]
        mock_poll.duration = 60
        mock_poll.poll_type = "single"

        with patch('app.agents.intervention_executor.poll_strategy') as mock_strategy:
            mock_strategy.generate_with_ai = AsyncMock(return_value=mock_poll)

            mock_db = AsyncMock()
            mock_db.add = MagicMock()
            mock_db.commit = AsyncMock()

            result = await executor._execute_poll(rec, mock_db)

            assert result['success'] is True
            assert 'intervention_id' in result
            mock_db.add.assert_called_once()
            mock_db.commit.assert_called_once()


@pytest.mark.asyncio
class TestExecuteChatPrompt:
    """Tests for chat prompt intervention execution"""

    async def test_execute_chat_prompt_success(self):
        """Test successful chat prompt execution"""
        mock_redis = MagicMock()
        mock_redis.publish = AsyncMock()
        executor = InterventionExecutor(redis_client=mock_redis)

        rec = InterventionRecommendation(
            intervention_type='CHAT_PROMPT',
            priority='MEDIUM',
            confidence=0.75,
            reason='Low chat activity',
            context={
                'session_id': str(uuid.uuid4()),
                'event_id': str(uuid.uuid4()),
                'prompt_type': 'discussion_starter'
            },
            estimated_impact=0.1
        )

        mock_db = AsyncMock()
        mock_db.add = MagicMock()
        mock_db.commit = AsyncMock()

        result = await executor._execute_chat_prompt(rec, mock_db)

        assert result['success'] is True
        assert 'intervention_id' in result


@pytest.mark.asyncio
class TestRecordOutcome:
    """Tests for recording intervention outcomes"""

    async def test_record_outcome_success(self):
        """Test recording a successful outcome"""
        mock_redis = MagicMock()
        executor = InterventionExecutor(redis_client=mock_redis)

        intervention_id = str(uuid.uuid4())

        # Add to pending
        executor.pending_interventions[intervention_id] = {
            'type': 'POLL',
            'session_id': str(uuid.uuid4()),
            'timestamp': datetime.now(timezone.utc)
        }

        mock_db = AsyncMock()
        mock_intervention = MagicMock()
        mock_intervention.outcome = None

        with patch('sqlalchemy.select') as mock_select:
            mock_result = MagicMock()
            mock_result.scalar_one_or_none = MagicMock(return_value=mock_intervention)
            mock_db.execute = AsyncMock(return_value=mock_result)

            outcome = {
                'success': True,
                'engagement_delta': 0.15,
                'participants': 25
            }

            await executor.record_outcome(intervention_id, outcome, mock_db)

            assert mock_intervention.outcome == outcome
            mock_db.commit.assert_called_once()
            assert intervention_id not in executor.pending_interventions

    async def test_record_outcome_intervention_not_found(self):
        """Test recording outcome for non-existent intervention"""
        executor = InterventionExecutor(redis_client=MagicMock())

        mock_db = AsyncMock()

        with patch('sqlalchemy.select') as mock_select:
            mock_result = MagicMock()
            mock_result.scalar_one_or_none = MagicMock(return_value=None)
            mock_db.execute = AsyncMock(return_value=mock_result)

            # Should not raise, just log warning
            await executor.record_outcome(str(uuid.uuid4()), {'success': True}, mock_db)


class TestLLMTimeoutConstant:
    """Tests for LLM timeout configuration"""

    def test_llm_timeout_is_reasonable(self):
        """Test that LLM timeout is set to a reasonable value"""
        assert LLM_TIMEOUT_SECONDS >= 10  # At least 10 seconds
        assert LLM_TIMEOUT_SECONDS <= 120  # At most 2 minutes
