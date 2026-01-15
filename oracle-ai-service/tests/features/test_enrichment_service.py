# tests/features/test_enrichment_service.py
"""
Unit tests for the profile enrichment service.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.agents.profile_enrichment.schemas import (
    EnrichmentInput,
    EnrichmentResult,
    EnrichmentStatus,
    ProfileTier,
)
from app.agents.profile_enrichment.fallback import (
    EnrichmentFallbackHandler,
    ProfileTierManager,
)
from app.core.rate_limiter import TokenBucketRateLimiter, UserRateLimiter
from app.core.circuit_breaker import CircuitBreaker, CircuitState
from app.core.exceptions import (
    RateLimitError,
    UserRateLimitError,
    CircuitBreakerOpenError,
)


class TestEnrichmentInput:
    """Tests for EnrichmentInput validation."""

    def test_valid_input(self):
        """Test valid input is accepted."""
        input_data = EnrichmentInput(
            user_id="user_123",
            name="John Doe",
            email="john@example.com",
            company="Acme Corp",
            role="Software Engineer",
        )
        assert input_data.user_id == "user_123"
        assert input_data.name == "John Doe"

    def test_name_sanitization(self):
        """Test that dangerous characters are removed from name."""
        input_data = EnrichmentInput(
            user_id="user_123",
            name="John <script>alert('xss')</script> Doe",
            email="john@example.com",
            company="Acme Corp",
            role="Engineer",
        )
        # Script tags should be removed
        assert "<script>" not in input_data.name
        assert "</script>" not in input_data.name

    def test_linkedin_url_validation(self):
        """Test LinkedIn URL validation."""
        # Valid URL
        input_data = EnrichmentInput(
            user_id="user_123",
            name="John Doe",
            email="john@example.com",
            company="Acme",
            role="Engineer",
            linkedin_url="https://linkedin.com/in/johndoe",
        )
        assert input_data.linkedin_url == "https://linkedin.com/in/johndoe"

        # Invalid URL should raise
        with pytest.raises(ValueError):
            EnrichmentInput(
                user_id="user_123",
                name="John Doe",
                email="john@example.com",
                company="Acme",
                role="Engineer",
                linkedin_url="not-a-valid-url",
            )

    def test_github_username_validation(self):
        """Test GitHub username validation."""
        # Valid username
        input_data = EnrichmentInput(
            user_id="user_123",
            name="John Doe",
            email="john@example.com",
            company="Acme",
            role="Engineer",
            github_username="john-doe123",
        )
        assert input_data.github_username == "john-doe123"

        # Invalid username should raise
        with pytest.raises(ValueError):
            EnrichmentInput(
                user_id="user_123",
                name="John Doe",
                email="john@example.com",
                company="Acme",
                role="Engineer",
                github_username="invalid..username",
            )

    def test_twitter_handle_validation(self):
        """Test Twitter handle validation."""
        # With @ prefix (should be stripped)
        input_data = EnrichmentInput(
            user_id="user_123",
            name="John Doe",
            email="john@example.com",
            company="Acme",
            role="Engineer",
            twitter_handle="@johndoe",
        )
        assert input_data.twitter_handle == "johndoe"


class TestEnrichmentResult:
    """Tests for EnrichmentResult creation."""

    def test_tier_1_rich(self):
        """Test TIER_1_RICH when 3+ sources found."""
        result = EnrichmentResult(
            user_id="user_123",
            status=EnrichmentStatus.COMPLETED,
            profile_tier=ProfileTier.TIER_1_RICH,
            sources_found=["linkedin", "github", "twitter"],
            missing_sources=["youtube", "instagram", "facebook"],
        )
        assert result.profile_tier == ProfileTier.TIER_1_RICH
        assert len(result.sources_found) == 3

    def test_tier_2_basic(self):
        """Test TIER_2_BASIC when 1-2 sources found."""
        result = EnrichmentResult(
            user_id="user_123",
            status=EnrichmentStatus.COMPLETED,
            profile_tier=ProfileTier.TIER_2_BASIC,
            sources_found=["linkedin"],
            missing_sources=["github", "twitter", "youtube", "instagram", "facebook"],
        )
        assert result.profile_tier == ProfileTier.TIER_2_BASIC
        assert len(result.sources_found) == 1

    def test_tier_3_manual(self):
        """Test TIER_3_MANUAL when no sources found."""
        result = EnrichmentResult(
            user_id="user_123",
            status=EnrichmentStatus.FAILED,
            profile_tier=ProfileTier.TIER_3_MANUAL,
            sources_found=[],
            missing_sources=["linkedin", "github", "twitter", "youtube", "instagram", "facebook"],
        )
        assert result.profile_tier == ProfileTier.TIER_3_MANUAL
        assert len(result.sources_found) == 0


class TestEnrichmentFallbackHandler:
    """Tests for EnrichmentFallbackHandler."""

    @pytest.mark.asyncio
    async def test_handle_rich_profile(self):
        """Test handling of rich profile (3+ sources)."""
        handler = EnrichmentFallbackHandler()

        result = EnrichmentResult(
            user_id="user_123",
            status=EnrichmentStatus.COMPLETED,
            profile_tier=ProfileTier.TIER_1_RICH,
            sources_found=["linkedin", "github", "twitter"],
            missing_sources=["youtube", "instagram", "facebook"],
        )

        tier = await handler.handle_enrichment_result("user_123", result)
        assert tier == ProfileTier.TIER_1_RICH

    @pytest.mark.asyncio
    async def test_handle_basic_profile(self):
        """Test handling of basic profile (1-2 sources)."""
        handler = EnrichmentFallbackHandler()

        result = EnrichmentResult(
            user_id="user_123",
            status=EnrichmentStatus.COMPLETED,
            profile_tier=ProfileTier.TIER_2_BASIC,
            sources_found=["linkedin"],
            missing_sources=["github", "twitter", "youtube", "instagram", "facebook"],
        )

        tier = await handler.handle_enrichment_result("user_123", result)
        assert tier == ProfileTier.TIER_2_BASIC

    @pytest.mark.asyncio
    async def test_handle_manual_profile(self):
        """Test handling of manual profile (no sources)."""
        handler = EnrichmentFallbackHandler()

        result = EnrichmentResult(
            user_id="user_123",
            status=EnrichmentStatus.FAILED,
            profile_tier=ProfileTier.TIER_3_MANUAL,
            sources_found=[],
            missing_sources=["linkedin", "github", "twitter", "youtube", "instagram", "facebook"],
        )

        tier = await handler.handle_enrichment_result("user_123", result)
        assert tier == ProfileTier.TIER_3_MANUAL


class TestProfileTierManager:
    """Tests for ProfileTierManager."""

    def test_get_tier_from_sources(self):
        """Test tier assignment based on source count."""
        assert ProfileTierManager.get_tier_from_sources(5) == ProfileTier.TIER_1_RICH
        assert ProfileTierManager.get_tier_from_sources(3) == ProfileTier.TIER_1_RICH
        assert ProfileTierManager.get_tier_from_sources(2) == ProfileTier.TIER_2_BASIC
        assert ProfileTierManager.get_tier_from_sources(1) == ProfileTier.TIER_2_BASIC
        assert ProfileTierManager.get_tier_from_sources(0) == ProfileTier.TIER_3_MANUAL

    def test_should_retry_enrichment(self):
        """Test retry logic for enrichment."""
        # Should retry pending with attempts remaining
        assert ProfileTierManager.should_retry_enrichment(
            ProfileTier.TIER_0_PENDING, attempts=0
        ) is True

        # Should NOT retry if already rich
        assert ProfileTierManager.should_retry_enrichment(
            ProfileTier.TIER_1_RICH, attempts=0
        ) is False

        # Should NOT retry if max attempts exceeded
        assert ProfileTierManager.should_retry_enrichment(
            ProfileTier.TIER_3_MANUAL, attempts=3
        ) is False


class TestTokenBucketRateLimiter:
    """Tests for TokenBucketRateLimiter."""

    @pytest.mark.asyncio
    async def test_acquire_success(self):
        """Test successful token acquisition."""
        limiter = TokenBucketRateLimiter(
            name="test",
            rate_limit=10,
            period_seconds=60,
        )

        # Should succeed
        result = await limiter.acquire()
        assert result is True

    @pytest.mark.asyncio
    async def test_acquire_rate_limit_exceeded(self):
        """Test rate limit exceeded."""
        limiter = TokenBucketRateLimiter(
            name="test",
            rate_limit=2,
            period_seconds=60,
        )

        # Exhaust tokens
        await limiter.acquire()
        await limiter.acquire()

        # Should raise
        with pytest.raises(RateLimitError):
            await limiter.acquire()

    @pytest.mark.asyncio
    async def test_get_remaining(self):
        """Test getting remaining tokens."""
        limiter = TokenBucketRateLimiter(
            name="test",
            rate_limit=10,
            period_seconds=60,
        )

        # Initially full
        remaining = await limiter.get_remaining()
        assert remaining == 10

        # After one acquisition
        await limiter.acquire()
        remaining = await limiter.get_remaining()
        assert remaining == 9


class TestUserRateLimiter:
    """Tests for UserRateLimiter."""

    @pytest.mark.asyncio
    async def test_acquire_per_user(self):
        """Test per-user rate limiting."""
        limiter = UserRateLimiter(
            name="test",
            rate_limit=2,
            period_seconds=60,
        )

        # User 1 can acquire
        await limiter.acquire("user_1")
        await limiter.acquire("user_1")

        # User 1 rate limited
        with pytest.raises(UserRateLimitError):
            await limiter.acquire("user_1")

        # User 2 not affected
        result = await limiter.acquire("user_2")
        assert result is True


class TestCircuitBreaker:
    """Tests for CircuitBreaker."""

    @pytest.mark.asyncio
    async def test_closed_state(self):
        """Test normal operation in closed state."""
        breaker = CircuitBreaker(name="test", fail_max=3, reset_timeout=60)

        assert breaker.is_closed is True

        async with breaker:
            pass  # Success

        assert breaker.is_closed is True

    @pytest.mark.asyncio
    async def test_open_after_failures(self):
        """Test circuit opens after max failures."""
        breaker = CircuitBreaker(name="test", fail_max=2, reset_timeout=60)

        # Fail twice
        for _ in range(2):
            try:
                async with breaker:
                    raise Exception("Simulated failure")
            except Exception:
                pass

        # Should be open
        assert breaker.is_open is True

        # Next call should fail fast
        with pytest.raises(CircuitBreakerOpenError):
            async with breaker:
                pass

    @pytest.mark.asyncio
    async def test_call_wrapper(self):
        """Test the call() method."""
        breaker = CircuitBreaker(name="test", fail_max=3, reset_timeout=60)

        async def success_func():
            return "success"

        result = await breaker.call(success_func)
        assert result == "success"

    def test_get_stats(self):
        """Test getting circuit breaker stats."""
        breaker = CircuitBreaker(name="test", fail_max=5, reset_timeout=30)

        stats = breaker.get_stats()
        assert stats["name"] == "test"
        assert stats["state"] == "closed"
        assert stats["failure_count"] == 0
        assert stats["fail_max"] == 5
