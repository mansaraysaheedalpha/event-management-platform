# app/core/rate_limiter.py
"""
Token bucket rate limiter for API calls.
Prevents cost spikes and protects external API rate limits.
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional

import redis.asyncio as aioredis

from app.core.config import settings
from app.core.exceptions import RateLimitError, UserRateLimitError

logger = logging.getLogger(__name__)


class TokenBucketRateLimiter:
    """
    Async token bucket rate limiter.

    Uses Redis for distributed rate limiting across multiple workers.
    Falls back to in-memory limiting if Redis is unavailable.
    """

    def __init__(
        self,
        name: str,
        rate_limit: int,
        period_seconds: int,
        redis_client: Optional[aioredis.Redis] = None,
    ):
        """
        Initialize rate limiter.

        Args:
            name: Identifier for this limiter (e.g., "tavily", "github")
            rate_limit: Maximum number of requests allowed in the period
            period_seconds: Time period in seconds
            redis_client: Optional Redis client for distributed limiting
        """
        self.name = name
        self.rate_limit = rate_limit
        self.period_seconds = period_seconds
        self.redis_client = redis_client

        # In-memory fallback
        self._tokens = float(rate_limit)
        self._last_refill = datetime.now(timezone.utc)
        self._lock = asyncio.Lock()

    @property
    def _redis_key(self) -> str:
        """Redis key for this rate limiter."""
        return f"rate_limit:{self.name}"

    async def acquire(self, cost: int = 1) -> bool:
        """
        Acquire tokens from the bucket.

        Args:
            cost: Number of tokens to consume (default 1)

        Returns:
            True if tokens acquired, raises RateLimitError otherwise

        Raises:
            RateLimitError: If rate limit exceeded
        """
        if self.redis_client:
            return await self._acquire_redis(cost)
        return await self._acquire_memory(cost)

    async def _acquire_redis(self, cost: int = 1) -> bool:
        """Acquire using Redis for distributed rate limiting."""
        try:
            key = self._redis_key
            now = datetime.now(timezone.utc).timestamp()

            # Lua script for atomic token bucket operation
            lua_script = """
            local key = KEYS[1]
            local rate_limit = tonumber(ARGV[1])
            local period = tonumber(ARGV[2])
            local cost = tonumber(ARGV[3])
            local now = tonumber(ARGV[4])

            -- Get current state
            local data = redis.call('HMGET', key, 'tokens', 'last_refill')
            local tokens = tonumber(data[1]) or rate_limit
            local last_refill = tonumber(data[2]) or now

            -- Calculate tokens to add based on elapsed time
            local elapsed = now - last_refill
            local refill_rate = rate_limit / period
            local tokens_to_add = elapsed * refill_rate

            -- Update tokens (capped at rate_limit)
            tokens = math.min(rate_limit, tokens + tokens_to_add)

            -- Check if we have enough tokens
            if tokens >= cost then
                tokens = tokens - cost
                redis.call('HMSET', key, 'tokens', tokens, 'last_refill', now)
                redis.call('EXPIRE', key, period * 2)
                return 1
            else
                redis.call('HMSET', key, 'tokens', tokens, 'last_refill', now)
                redis.call('EXPIRE', key, period * 2)
                return 0
            end
            """

            result = await self.redis_client.eval(
                lua_script,
                1,
                key,
                self.rate_limit,
                self.period_seconds,
                cost,
                now,
            )

            if result == 1:
                return True

            # Calculate retry after
            retry_after = int(self.period_seconds / self.rate_limit * cost)
            raise RateLimitError(
                service_name=self.name,
                limit=self.rate_limit,
                period_seconds=self.period_seconds,
                retry_after_seconds=retry_after,
            )

        except aioredis.RedisError as e:
            logger.warning(f"Redis error in rate limiter, falling back to memory: {e}")
            return await self._acquire_memory(cost)

    async def _acquire_memory(self, cost: int = 1) -> bool:
        """Acquire using in-memory token bucket (single-instance only)."""
        async with self._lock:
            now = datetime.now(timezone.utc)

            # Refill tokens based on elapsed time
            elapsed = (now - self._last_refill).total_seconds()
            refill_rate = self.rate_limit / self.period_seconds
            tokens_to_add = elapsed * refill_rate

            self._tokens = min(float(self.rate_limit), self._tokens + tokens_to_add)
            self._last_refill = now

            # Check if we have enough tokens
            if self._tokens >= cost:
                self._tokens -= cost
                return True

            # Calculate retry after
            retry_after = int(self.period_seconds / self.rate_limit * cost)
            raise RateLimitError(
                service_name=self.name,
                limit=self.rate_limit,
                period_seconds=self.period_seconds,
                retry_after_seconds=retry_after,
            )

    async def get_remaining(self) -> int:
        """Get remaining tokens in the bucket."""
        if self.redis_client:
            try:
                data = await self.redis_client.hget(self._redis_key, "tokens")
                return int(float(data)) if data else self.rate_limit
            except aioredis.RedisError:
                pass
        return int(self._tokens)


class UserRateLimiter:
    """
    Per-user rate limiter to prevent abuse.

    Tracks rate limits per user ID using Redis.
    """

    def __init__(
        self,
        name: str,
        rate_limit: int,
        period_seconds: int,
        redis_client: Optional[aioredis.Redis] = None,
    ):
        self.name = name
        self.rate_limit = rate_limit
        self.period_seconds = period_seconds
        self.redis_client = redis_client

        # In-memory fallback (per-user tracking)
        self._user_tokens: dict[str, float] = {}
        self._user_last_refill: dict[str, datetime] = {}
        self._lock = asyncio.Lock()

    def _redis_key(self, user_id: str) -> str:
        """Redis key for user rate limit."""
        return f"rate_limit:{self.name}:user:{user_id}"

    async def acquire(self, user_id: str, cost: int = 1) -> bool:
        """
        Acquire tokens for a specific user.

        Args:
            user_id: User identifier
            cost: Number of tokens to consume

        Returns:
            True if acquired, raises UserRateLimitError otherwise
        """
        if self.redis_client:
            return await self._acquire_redis(user_id, cost)
        return await self._acquire_memory(user_id, cost)

    async def _acquire_redis(self, user_id: str, cost: int = 1) -> bool:
        """Acquire using Redis."""
        try:
            key = self._redis_key(user_id)
            now = datetime.now(timezone.utc).timestamp()

            # Use sliding window counter for simplicity
            pipe = self.redis_client.pipeline()

            # Remove old entries outside the window
            window_start = now - self.period_seconds
            await pipe.zremrangebyscore(key, 0, window_start)

            # Count requests in current window
            await pipe.zcard(key)

            results = await pipe.execute()
            current_count = results[1]

            if current_count < self.rate_limit:
                # Add new request
                await self.redis_client.zadd(key, {str(now): now})
                await self.redis_client.expire(key, self.period_seconds * 2)
                return True

            raise UserRateLimitError(
                user_id=user_id,
                limit=self.rate_limit,
                period_seconds=self.period_seconds,
            )

        except aioredis.RedisError as e:
            logger.warning(f"Redis error in user rate limiter: {e}")
            return await self._acquire_memory(user_id, cost)

    async def _acquire_memory(self, user_id: str, cost: int = 1) -> bool:
        """Acquire using in-memory tracking."""
        async with self._lock:
            now = datetime.now(timezone.utc)

            # Initialize if new user
            if user_id not in self._user_tokens:
                self._user_tokens[user_id] = float(self.rate_limit)
                self._user_last_refill[user_id] = now

            # Refill tokens
            elapsed = (now - self._user_last_refill[user_id]).total_seconds()
            refill_rate = self.rate_limit / self.period_seconds
            tokens_to_add = elapsed * refill_rate

            self._user_tokens[user_id] = min(
                float(self.rate_limit),
                self._user_tokens[user_id] + tokens_to_add,
            )
            self._user_last_refill[user_id] = now

            if self._user_tokens[user_id] >= cost:
                self._user_tokens[user_id] -= cost
                return True

            raise UserRateLimitError(
                user_id=user_id,
                limit=self.rate_limit,
                period_seconds=self.period_seconds,
            )

    async def log_suspicious_activity(self, user_id: str, action: str) -> None:
        """Log suspicious rate limit patterns."""
        logger.warning(
            f"Suspicious activity detected - user: {user_id}, action: {action}, "
            f"limiter: {self.name}"
        )


# ===========================================
# Global Rate Limiter Instances (Singletons)
# ===========================================

_redis_client: Optional[aioredis.Redis] = None
_redis_client_initialized: bool = False

# Singleton instances - MUST be reused to maintain token counts
_tavily_limiter: Optional[TokenBucketRateLimiter] = None
_github_limiter: Optional[TokenBucketRateLimiter] = None
_llm_limiter: Optional[TokenBucketRateLimiter] = None
_user_enrichment_limiter: Optional[UserRateLimiter] = None
_limiter_lock = asyncio.Lock()


async def get_redis_client() -> Optional[aioredis.Redis]:
    """Get or create Redis client for rate limiting."""
    global _redis_client, _redis_client_initialized

    if _redis_client_initialized:
        return _redis_client

    async with _limiter_lock:
        # Double-check after acquiring lock
        if _redis_client_initialized:
            return _redis_client

        try:
            _redis_client = await aioredis.from_url(
                settings.REDIS_URL,
                encoding="utf-8",
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5,
            )
            # Test connection
            await _redis_client.ping()
            logger.info("Redis client connected for rate limiting")
        except Exception as e:
            logger.warning(f"Could not connect to Redis for rate limiting: {e}")
            _redis_client = None
        finally:
            _redis_client_initialized = True

    return _redis_client


async def get_tavily_limiter() -> TokenBucketRateLimiter:
    """Get Tavily API rate limiter (singleton)."""
    global _tavily_limiter

    if _tavily_limiter is not None:
        return _tavily_limiter

    async with _limiter_lock:
        if _tavily_limiter is not None:
            return _tavily_limiter

        redis_client = await get_redis_client()
        _tavily_limiter = TokenBucketRateLimiter(
            name="tavily",
            rate_limit=settings.TAVILY_RATE_LIMIT,
            period_seconds=settings.TAVILY_RATE_PERIOD_SECONDS,
            redis_client=redis_client,
        )
        return _tavily_limiter


async def get_github_limiter() -> TokenBucketRateLimiter:
    """Get GitHub API rate limiter (singleton)."""
    global _github_limiter

    if _github_limiter is not None:
        return _github_limiter

    async with _limiter_lock:
        if _github_limiter is not None:
            return _github_limiter

        redis_client = await get_redis_client()
        _github_limiter = TokenBucketRateLimiter(
            name="github",
            rate_limit=settings.GITHUB_RATE_LIMIT,
            period_seconds=settings.GITHUB_RATE_PERIOD_SECONDS,
            redis_client=redis_client,
        )
        return _github_limiter


async def get_llm_limiter() -> TokenBucketRateLimiter:
    """Get LLM API rate limiter (singleton)."""
    global _llm_limiter

    if _llm_limiter is not None:
        return _llm_limiter

    async with _limiter_lock:
        if _llm_limiter is not None:
            return _llm_limiter

        redis_client = await get_redis_client()
        _llm_limiter = TokenBucketRateLimiter(
            name="llm",
            rate_limit=settings.LLM_RATE_LIMIT,
            period_seconds=settings.LLM_RATE_PERIOD_SECONDS,
            redis_client=redis_client,
        )
        return _llm_limiter


async def get_user_enrichment_limiter() -> UserRateLimiter:
    """Get per-user enrichment rate limiter (singleton)."""
    global _user_enrichment_limiter

    if _user_enrichment_limiter is not None:
        return _user_enrichment_limiter

    async with _limiter_lock:
        if _user_enrichment_limiter is not None:
            return _user_enrichment_limiter

        redis_client = await get_redis_client()
        _user_enrichment_limiter = UserRateLimiter(
            name="enrichment",
            rate_limit=settings.USER_ENRICHMENT_RATE_LIMIT,
            period_seconds=settings.USER_ENRICHMENT_RATE_PERIOD_SECONDS,
            redis_client=redis_client,
        )
        return _user_enrichment_limiter


async def close_rate_limiters() -> None:
    """Close Redis connection on shutdown."""
    global _redis_client, _redis_client_initialized

    if _redis_client is not None:
        await _redis_client.close()
        _redis_client = None
        _redis_client_initialized = False
        logger.info("Rate limiter Redis client closed")
