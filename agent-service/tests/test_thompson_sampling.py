"""
Unit tests for Thompson Sampling algorithm
"""
import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from app.agents.thompson_sampling import (
    ThompsonSampling,
    InterventionType,
    AnomalyType,
    ContextKey,
    InterventionStats,
    get_thompson_sampling,
)


class TestContextKey:
    """Tests for ContextKey dataclass"""

    def test_context_key_to_string(self):
        """Test context key string representation"""
        context = ContextKey(
            anomaly_type=AnomalyType.SUDDEN_DROP,
            engagement_bucket='low',
            session_size_bucket='medium'
        )
        assert context.to_string() == "SUDDEN_DROP_low_medium"

    def test_context_key_different_values(self):
        """Test different context key combinations"""
        contexts = [
            (AnomalyType.GRADUAL_DECLINE, 'critical', 'small'),
            (AnomalyType.MASS_EXIT, 'medium', 'large'),
            (AnomalyType.LOW_ENGAGEMENT, 'low', 'small'),
        ]
        for anomaly, engagement, size in contexts:
            context = ContextKey(anomaly, engagement, size)
            expected = f"{anomaly.value}_{engagement}_{size}"
            assert context.to_string() == expected


class TestInterventionStats:
    """Tests for InterventionStats dataclass"""

    def test_success_rate_calculation(self):
        """Test success rate is calculated correctly"""
        stats = InterventionStats(
            intervention_type=InterventionType.POLL,
            context=ContextKey(AnomalyType.SUDDEN_DROP, 'low', 'medium'),
            alpha=5.0,  # 4 successes + 1 prior
            beta=2.0,   # 1 failure + 1 prior
            total_attempts=5,
            last_updated=datetime.now(timezone.utc)
        )
        # Success rate = alpha / (alpha + beta) = 5 / 7 ≈ 0.714
        assert abs(stats.success_rate - 0.714) < 0.01

    def test_success_rate_with_uniform_prior(self):
        """Test success rate with uniform prior (alpha=1, beta=1)"""
        stats = InterventionStats(
            intervention_type=InterventionType.CHAT_PROMPT,
            context=ContextKey(AnomalyType.LOW_ENGAGEMENT, 'critical', 'small'),
            alpha=1.0,
            beta=1.0,
            total_attempts=0,
            last_updated=datetime.now(timezone.utc)
        )
        assert stats.success_rate == 0.5

    def test_sample_returns_value_in_range(self):
        """Test that sample returns value between 0 and 1"""
        stats = InterventionStats(
            intervention_type=InterventionType.NOTIFICATION,
            context=ContextKey(AnomalyType.MASS_EXIT, 'low', 'large'),
            alpha=3.0,
            beta=2.0,
            total_attempts=3,
            last_updated=datetime.now(timezone.utc)
        )
        for _ in range(100):
            sample = stats.sample()
            assert 0 <= sample <= 1


class TestThompsonSampling:
    """Tests for ThompsonSampling class"""

    def test_initialization(self):
        """Test Thompson Sampling initializes correctly"""
        ts = ThompsonSampling(alpha_prior=1.0, beta_prior=1.0)
        assert ts.alpha_prior == 1.0
        assert ts.beta_prior == 1.0
        assert len(ts.stats) == 0

    def test_create_context_critical_engagement(self):
        """Test context creation with critical engagement"""
        ts = ThompsonSampling()
        context = ts.create_context(
            anomaly_type=AnomalyType.SUDDEN_DROP,
            engagement_score=20.0,  # < 30 = critical
            active_users=5  # < 10 = small
        )
        assert context.engagement_bucket == 'critical'
        assert context.session_size_bucket == 'small'

    def test_create_context_low_engagement(self):
        """Test context creation with low engagement"""
        ts = ThompsonSampling()
        context = ts.create_context(
            anomaly_type=AnomalyType.GRADUAL_DECLINE,
            engagement_score=40.0,  # 30-50 = low
            active_users=25  # 10-50 = medium
        )
        assert context.engagement_bucket == 'low'
        assert context.session_size_bucket == 'medium'

    def test_create_context_medium_engagement(self):
        """Test context creation with medium engagement"""
        ts = ThompsonSampling()
        context = ts.create_context(
            anomaly_type=AnomalyType.LOW_ENGAGEMENT,
            engagement_score=60.0,  # >= 50 = medium
            active_users=100  # >= 50 = large
        )
        assert context.engagement_bucket == 'medium'
        assert context.session_size_bucket == 'large'

    def test_select_intervention_initializes_context(self):
        """Test that selecting intervention initializes stats for new context"""
        ts = ThompsonSampling()
        context = ts.create_context(AnomalyType.SUDDEN_DROP, 25.0, 15)

        intervention, sample = ts.select_intervention(context)

        # Should have stats for all intervention types
        context_key = context.to_string()
        assert context_key in ts.stats
        assert len(ts.stats[context_key]) == len(InterventionType)

    def test_select_intervention_returns_valid_type(self):
        """Test that selected intervention is a valid type"""
        ts = ThompsonSampling()
        context = ts.create_context(AnomalyType.MASS_EXIT, 45.0, 30)

        intervention, sample = ts.select_intervention(context)

        assert intervention in InterventionType
        assert 0 <= sample <= 1

    def test_select_intervention_with_limited_options(self):
        """Test selecting from limited intervention options"""
        ts = ThompsonSampling()
        context = ts.create_context(AnomalyType.LOW_ENGAGEMENT, 35.0, 8)
        available = [InterventionType.POLL, InterventionType.CHAT_PROMPT]

        intervention, sample = ts.select_intervention(context, available)

        assert intervention in available

    def test_update_increases_alpha_on_success(self):
        """Test that successful update increases alpha"""
        ts = ThompsonSampling()
        context = ts.create_context(AnomalyType.SUDDEN_DROP, 25.0, 20)
        intervention = InterventionType.POLL

        # Initialize by selecting
        ts.select_intervention(context)

        initial_alpha = ts.stats[context.to_string()][intervention].alpha

        # Update with success
        ts.update(context, intervention, success=True)

        new_alpha = ts.stats[context.to_string()][intervention].alpha
        assert new_alpha > initial_alpha

    def test_update_increases_beta_on_failure(self):
        """Test that failed update increases beta"""
        ts = ThompsonSampling()
        context = ts.create_context(AnomalyType.GRADUAL_DECLINE, 40.0, 50)
        intervention = InterventionType.NOTIFICATION

        # Initialize by selecting
        ts.select_intervention(context)

        initial_beta = ts.stats[context.to_string()][intervention].beta

        # Update with failure
        ts.update(context, intervention, success=False)

        new_beta = ts.stats[context.to_string()][intervention].beta
        assert new_beta > initial_beta

    def test_update_with_reward(self):
        """Test update with custom reward value"""
        ts = ThompsonSampling()
        context = ts.create_context(AnomalyType.MASS_EXIT, 20.0, 100)
        intervention = InterventionType.GAMIFICATION

        ts.select_intervention(context)
        initial_alpha = ts.stats[context.to_string()][intervention].alpha

        # Update with partial reward
        ts.update(context, intervention, success=True, reward=0.5)

        new_alpha = ts.stats[context.to_string()][intervention].alpha
        assert new_alpha == initial_alpha + 0.5

    def test_get_best_intervention(self):
        """Test getting best intervention based on success rate"""
        ts = ThompsonSampling()
        context = ts.create_context(AnomalyType.SUDDEN_DROP, 25.0, 30)

        # Initialize and bias one intervention
        ts.select_intervention(context)

        # Add several successes for POLL
        for _ in range(10):
            ts.update(context, InterventionType.POLL, success=True)

        best, rate = ts.get_best_intervention(context)
        assert best == InterventionType.POLL
        assert rate > 0.5

    def test_export_import_stats(self):
        """Test exporting and importing statistics"""
        ts = ThompsonSampling()
        context = ts.create_context(AnomalyType.LOW_ENGAGEMENT, 35.0, 25)

        # Build up some stats
        ts.select_intervention(context)
        ts.update(context, InterventionType.POLL, success=True)
        ts.update(context, InterventionType.POLL, success=True)
        ts.update(context, InterventionType.CHAT_PROMPT, success=False)

        # Export
        exported = ts.export_stats()
        assert context.to_string() in exported

        # Create new instance and import
        ts2 = ThompsonSampling()
        ts2.import_stats(exported)

        # Verify stats match
        context_key = context.to_string()
        assert ts2.stats[context_key][InterventionType.POLL].alpha == \
               ts.stats[context_key][InterventionType.POLL].alpha


class TestGlobalInstance:
    """Tests for global Thompson Sampling instance"""

    def test_get_thompson_sampling_singleton(self):
        """Test that get_thompson_sampling returns same instance"""
        # Note: This test may be affected by other tests
        ts1 = get_thompson_sampling()
        ts2 = get_thompson_sampling()
        assert ts1 is ts2


@pytest.mark.asyncio
class TestThompsonSamplingRedis:
    """Tests for Redis persistence (requires mocking)"""

    async def test_save_to_redis(self):
        """Test saving stats to Redis"""
        ts = ThompsonSampling()
        context = ts.create_context(AnomalyType.SUDDEN_DROP, 25.0, 20)
        ts.select_intervention(context)

        mock_redis = MagicMock()
        mock_redis.client = AsyncMock()
        mock_redis.client.set = AsyncMock(return_value=True)

        with patch('app.core.redis_client.redis_client', mock_redis):
            result = await ts.save_to_redis()

            assert result is True
            mock_redis.client.set.assert_called_once()

    async def test_load_from_redis_no_data(self):
        """Test loading from Redis when no data exists"""
        ts = ThompsonSampling()

        mock_redis = MagicMock()
        mock_redis.client = AsyncMock()
        mock_redis.client.get = AsyncMock(return_value=None)

        with patch('app.core.redis_client.redis_client', mock_redis):
            result = await ts.load_from_redis()

            assert result is False

    async def test_load_from_redis_with_data(self):
        """Test loading from Redis with existing data"""
        ts = ThompsonSampling()

        mock_data = '{"SUDDEN_DROP_low_medium": {"POLL": {"alpha": 3.0, "beta": 2.0, "total_attempts": 3, "last_updated": "2024-01-01T00:00:00+00:00"}}}'

        mock_redis = MagicMock()
        mock_redis.client = AsyncMock()
        mock_redis.client.get = AsyncMock(return_value=mock_data)

        with patch('app.core.redis_client.redis_client', mock_redis):
            result = await ts.load_from_redis()

            assert result is True
            assert "SUDDEN_DROP_low_medium" in ts.stats
