"""
Rate Limiter and Cost Control Middleware

Provides:
- Request rate limiting per endpoint
- LLM cost tracking and limits
- Token usage monitoring
- Circuit breaker for expensive operations
"""

import logging
import time
from typing import Dict, Optional, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from collections import defaultdict
import asyncio

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from app.middleware.error_handler import RateLimitError

logger = logging.getLogger(__name__)


@dataclass
class RateLimitConfig:
    """Rate limit configuration"""
    requests_per_minute: int = 60
    requests_per_hour: int = 1000
    burst_size: int = 10  # Allow bursts up to this size


@dataclass
class CostLimit:
    """Cost limit configuration"""
    daily_limit_usd: float = 100.0
    hourly_limit_usd: float = 20.0
    per_request_limit_usd: float = 2.0
    warning_threshold: float = 0.8  # Warn at 80% of limit


@dataclass
class TokenBucket:
    """Token bucket for rate limiting"""
    capacity: int
    tokens: float
    refill_rate: float  # tokens per second
    last_refill: float = field(default_factory=time.time)

    def consume(self, tokens: int = 1) -> bool:
        """Try to consume tokens. Returns True if successful."""
        self._refill()

        if self.tokens >= tokens:
            self.tokens -= tokens
            return True
        return False

    def _refill(self):
        """Refill tokens based on time elapsed"""
        now = time.time()
        elapsed = now - self.last_refill
        self.tokens = min(self.capacity, self.tokens + elapsed * self.refill_rate)
        self.last_refill = now

    def time_until_ready(self) -> float:
        """Time in seconds until a token is available"""
        if self.tokens >= 1:
            return 0.0
        return (1 - self.tokens) / self.refill_rate


class RateLimiter:
    """
    Rate limiter using token bucket algorithm.

    Supports:
    - Per-endpoint rate limits
    - Per-client rate limits (by IP or API key)
    - Configurable burst sizes
    """

    def __init__(self):
        self.buckets: Dict[str, TokenBucket] = {}
        self.configs: Dict[str, RateLimitConfig] = {
            "default": RateLimitConfig(
                requests_per_minute=60,
                requests_per_hour=1000,
                burst_size=10
            ),
            "llm": RateLimitConfig(
                requests_per_minute=30,
                requests_per_hour=500,
                burst_size=5
            ),
            "interventions": RateLimitConfig(
                requests_per_minute=10,
                requests_per_hour=200,
                burst_size=3
            )
        }

    def get_bucket_key(self, client_id: str, endpoint_type: str) -> str:
        """Generate unique bucket key"""
        return f"{endpoint_type}:{client_id}"

    def get_or_create_bucket(self, key: str, config: RateLimitConfig) -> TokenBucket:
        """Get or create token bucket for a key"""
        if key not in self.buckets:
            # Calculate refill rate (tokens per second)
            refill_rate = config.requests_per_minute / 60.0

            self.buckets[key] = TokenBucket(
                capacity=config.burst_size,
                tokens=config.burst_size,
                refill_rate=refill_rate
            )

        return self.buckets[key]

    def check_rate_limit(
        self,
        client_id: str,
        endpoint_type: str = "default"
    ) -> Tuple[bool, Optional[int]]:
        """
        Check if request is within rate limit.

        Returns:
            (allowed, retry_after_seconds)
        """
        config = self.configs.get(endpoint_type, self.configs["default"])
        bucket_key = self.get_bucket_key(client_id, endpoint_type)
        bucket = self.get_or_create_bucket(bucket_key, config)

        if bucket.consume():
            return True, None
        else:
            retry_after = int(bucket.time_until_ready()) + 1
            logger.warning(
                f"Rate limit exceeded for {client_id} on {endpoint_type}",
                extra={
                    "client_id": client_id,
                    "endpoint_type": endpoint_type,
                    "retry_after": retry_after
                }
            )
            return False, retry_after


class CostTracker:
    """
    Track and limit LLM API costs.

    Monitors:
    - Token usage
    - Estimated costs
    - Cost per time period
    """

    # Pricing (as of 2026-01-04)
    PRICING = {
        "claude-sonnet-4-5": {
            "input": 3.00 / 1_000_000,  # $3 per MTok
            "output": 15.00 / 1_000_000,  # $15 per MTok
            "cache_write": 3.75 / 1_000_000,  # $3.75 per MTok
            "cache_read": 0.30 / 1_000_000  # $0.30 per MTok
        },
        "claude-3-5-haiku": {
            "input": 1.00 / 1_000_000,  # $1 per MTok
            "output": 5.00 / 1_000_000,  # $5 per MTok
        }
    }

    def __init__(self, config: Optional[CostLimit] = None):
        self.config = config or CostLimit()

        # Cost tracking by time period
        self.hourly_costs: Dict[str, float] = defaultdict(float)  # hour -> cost
        self.daily_costs: Dict[str, float] = defaultdict(float)   # day -> cost
        self.total_cost: float = 0.0

        # Token tracking
        self.total_tokens: Dict[str, int] = defaultdict(int)  # model -> tokens

    def calculate_cost(
        self,
        model: str,
        input_tokens: int,
        output_tokens: int,
        cache_write_tokens: int = 0,
        cache_read_tokens: int = 0
    ) -> float:
        """Calculate cost for a request"""

        if model not in self.PRICING:
            logger.warning(f"Unknown model for cost calculation: {model}")
            return 0.0

        pricing = self.PRICING[model]

        cost = (
            input_tokens * pricing["input"] +
            output_tokens * pricing["output"]
        )

        # Add cache costs if applicable
        if "cache_write" in pricing:
            cost += cache_write_tokens * pricing["cache_write"]
        if "cache_read" in pricing:
            cost += cache_read_tokens * pricing["cache_read"]

        return cost

    def track_usage(
        self,
        model: str,
        input_tokens: int,
        output_tokens: int,
        cache_write_tokens: int = 0,
        cache_read_tokens: int = 0
    ) -> Dict:
        """
        Track usage and check against limits.

        Returns:
            Dict with cost info and limit status
        """
        cost = self.calculate_cost(
            model, input_tokens, output_tokens,
            cache_write_tokens, cache_read_tokens
        )

        # Update tracking
        now = datetime.utcnow()
        hour_key = now.strftime("%Y-%m-%d-%H")
        day_key = now.strftime("%Y-%m-%d")

        self.hourly_costs[hour_key] += cost
        self.daily_costs[day_key] += cost
        self.total_cost += cost

        total_tokens = input_tokens + output_tokens + cache_write_tokens + cache_read_tokens
        self.total_tokens[model] += total_tokens

        # Check limits
        hourly_usage = self.hourly_costs[hour_key]
        daily_usage = self.daily_costs[day_key]

        hourly_pct = hourly_usage / self.config.hourly_limit_usd
        daily_pct = daily_usage / self.config.daily_limit_usd

        # Determine if we should warn or block
        exceeds_hourly = hourly_usage >= self.config.hourly_limit_usd
        exceeds_daily = daily_usage >= self.config.daily_limit_usd
        exceeds_per_request = cost >= self.config.per_request_limit_usd

        should_warn = (
            hourly_pct >= self.config.warning_threshold or
            daily_pct >= self.config.warning_threshold
        )

        if should_warn:
            logger.warning(
                "Cost limit warning",
                extra={
                    "hourly_cost": hourly_usage,
                    "daily_cost": daily_usage,
                    "hourly_pct": hourly_pct,
                    "daily_pct": daily_pct,
                    "model": model
                }
            )

        if exceeds_hourly or exceeds_daily or exceeds_per_request:
            logger.error(
                "Cost limit exceeded",
                extra={
                    "hourly_cost": hourly_usage,
                    "daily_cost": daily_usage,
                    "request_cost": cost,
                    "exceeds_hourly": exceeds_hourly,
                    "exceeds_daily": exceeds_daily,
                    "exceeds_per_request": exceeds_per_request,
                    "model": model
                }
            )

        return {
            "cost": cost,
            "hourly_cost": hourly_usage,
            "daily_cost": daily_usage,
            "total_cost": self.total_cost,
            "hourly_limit": self.config.hourly_limit_usd,
            "daily_limit": self.config.daily_limit_usd,
            "hourly_pct": hourly_pct,
            "daily_pct": daily_pct,
            "exceeds_limit": exceeds_hourly or exceeds_daily or exceeds_per_request,
            "warning": should_warn
        }

    def check_can_proceed(self, estimated_cost: float = 0.5) -> Tuple[bool, str]:
        """
        Check if a request can proceed given estimated cost.

        Returns:
            (can_proceed, reason)
        """
        now = datetime.utcnow()
        hour_key = now.strftime("%Y-%m-%d-%H")
        day_key = now.strftime("%Y-%m-%d")

        hourly_usage = self.hourly_costs[hour_key]
        daily_usage = self.daily_costs[day_key]

        # Check if adding estimated cost would exceed limits
        if hourly_usage + estimated_cost > self.config.hourly_limit_usd:
            return False, f"Hourly cost limit reached (${hourly_usage:.2f}/${self.config.hourly_limit_usd:.2f})"

        if daily_usage + estimated_cost > self.config.daily_limit_usd:
            return False, f"Daily cost limit reached (${daily_usage:.2f}/${self.config.daily_limit_usd:.2f})"

        if estimated_cost > self.config.per_request_limit_usd:
            return False, f"Request cost too high (${estimated_cost:.2f} > ${self.config.per_request_limit_usd:.2f})"

        return True, ""

    def get_stats(self) -> Dict:
        """Get cost statistics"""
        now = datetime.utcnow()
        hour_key = now.strftime("%Y-%m-%d-%H")
        day_key = now.strftime("%Y-%m-%d")

        return {
            "hourly_cost": self.hourly_costs[hour_key],
            "daily_cost": self.daily_costs[day_key],
            "total_cost": self.total_cost,
            "hourly_limit": self.config.hourly_limit_usd,
            "daily_limit": self.config.daily_limit_usd,
            "tokens_by_model": dict(self.total_tokens)
        }


# Global instances
rate_limiter = RateLimiter()
cost_tracker = CostTracker()


async def rate_limit_middleware(request: Request, call_next):
    """Rate limiting middleware"""

    # Extract client identifier (IP or API key)
    client_id = request.client.host if request.client else "unknown"

    # Determine endpoint type
    path = request.url.path
    if "/api/v1/interventions" in path:
        endpoint_type = "interventions"
    elif "/llm" in path or "/generate" in path:
        endpoint_type = "llm"
    else:
        endpoint_type = "default"

    # Check rate limit
    allowed, retry_after = rate_limiter.check_rate_limit(client_id, endpoint_type)

    if not allowed:
        return JSONResponse(
            status_code=429,
            content={
                "error": {
                    "category": "rate_limit_error",
                    "message": "Rate limit exceeded. Please slow down.",
                    "retry_after": retry_after,
                    "timestamp": datetime.utcnow().isoformat()
                }
            },
            headers={"Retry-After": str(retry_after)}
        )

    # Process request
    response = await call_next(request)
    return response


def check_cost_limit(estimated_cost: float = 0.5):
    """
    Decorator to check cost limits before expensive operations.

    Usage:
        @check_cost_limit(estimated_cost=1.0)
        async def generate_content(...):
            ...
    """
    def decorator(func):
        async def wrapper(*args, **kwargs):
            can_proceed, reason = cost_tracker.check_can_proceed(estimated_cost)

            if not can_proceed:
                raise RateLimitError(
                    message=f"Cost limit exceeded: {reason}",
                    retry_after=3600  # Try again in 1 hour
                )

            return await func(*args, **kwargs)

        return wrapper
    return decorator
