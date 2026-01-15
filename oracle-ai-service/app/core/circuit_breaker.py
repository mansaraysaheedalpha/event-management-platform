# app/core/circuit_breaker.py
"""
Circuit breaker pattern for external API calls.
Prevents cascade failures when external services are down.
"""

import asyncio
import logging
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Optional, TypeVar

from app.core.config import settings
from app.core.exceptions import CircuitBreakerOpenError

logger = logging.getLogger(__name__)

T = TypeVar("T")


class CircuitState(Enum):
    """Circuit breaker states."""

    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Failing, reject requests
    HALF_OPEN = "half_open"  # Testing if service recovered


class CircuitBreaker:
    """
    Async circuit breaker for external API calls.

    States:
    - CLOSED: Normal operation, tracking failures
    - OPEN: Service unavailable, fast-fail all requests
    - HALF_OPEN: Testing recovery, allow limited requests

    Usage:
        breaker = CircuitBreaker("tavily")

        async with breaker:
            result = await external_api_call()
    """

    def __init__(
        self,
        name: str,
        fail_max: Optional[int] = None,
        reset_timeout: Optional[int] = None,
        exclude_exceptions: Optional[tuple] = None,
    ):
        """
        Initialize circuit breaker.

        Args:
            name: Service identifier
            fail_max: Failures before opening circuit
            reset_timeout: Seconds before attempting to close
            exclude_exceptions: Exceptions that don't count as failures
        """
        self.name = name
        self.fail_max = fail_max or settings.CIRCUIT_BREAKER_FAIL_MAX
        self.reset_timeout = reset_timeout or settings.CIRCUIT_BREAKER_TIMEOUT
        self.exclude_exceptions = exclude_exceptions or ()

        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._last_failure_time: Optional[datetime] = None
        self._lock = asyncio.Lock()

    @property
    def state(self) -> CircuitState:
        """Get current circuit state."""
        return self._state

    @property
    def is_closed(self) -> bool:
        """Check if circuit is closed (normal operation)."""
        return self._state == CircuitState.CLOSED

    @property
    def is_open(self) -> bool:
        """Check if circuit is open (failing)."""
        return self._state == CircuitState.OPEN

    async def __aenter__(self):
        """Context manager entry - check if request allowed."""
        await self._before_call()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - record success/failure."""
        if exc_type is None:
            await self._on_success()
        elif not self._is_excluded_exception(exc_type):
            await self._on_failure(exc_val)
        return False  # Don't suppress exceptions

    async def call(self, func: Callable[..., T], *args, **kwargs) -> T:
        """
        Execute function through circuit breaker.

        Args:
            func: Async function to execute
            *args, **kwargs: Arguments to pass to function

        Returns:
            Function result

        Raises:
            CircuitBreakerOpenError: If circuit is open
            Exception: Any exception from the function
        """
        async with self:
            return await func(*args, **kwargs)

    async def _before_call(self) -> None:
        """Check circuit state before allowing call."""
        async with self._lock:
            if self._state == CircuitState.CLOSED:
                return

            if self._state == CircuitState.OPEN:
                # Check if timeout has elapsed
                if self._should_attempt_reset():
                    self._state = CircuitState.HALF_OPEN
                    logger.info(
                        f"Circuit breaker {self.name} entering HALF_OPEN state"
                    )
                    return
                raise CircuitBreakerOpenError(self.name)

            # HALF_OPEN - allow the call to test recovery
            return

    async def _on_success(self) -> None:
        """Handle successful call."""
        async with self._lock:
            if self._state == CircuitState.HALF_OPEN:
                # Service recovered, close circuit
                self._reset()
                logger.info(
                    f"Circuit breaker {self.name} recovered, closing circuit"
                )
            elif self._state == CircuitState.CLOSED:
                # Reset failure count on success
                self._failure_count = 0

    async def _on_failure(self, exception: Exception) -> None:
        """Handle failed call."""
        async with self._lock:
            self._failure_count += 1
            self._last_failure_time = datetime.now(timezone.utc)

            logger.warning(
                f"Circuit breaker {self.name} failure {self._failure_count}/{self.fail_max}: "
                f"{type(exception).__name__}: {exception}"
            )

            if self._state == CircuitState.HALF_OPEN:
                # Failed during recovery test, reopen
                self._state = CircuitState.OPEN
                logger.warning(
                    f"Circuit breaker {self.name} reopened after failed recovery"
                )

            elif self._state == CircuitState.CLOSED:
                if self._failure_count >= self.fail_max:
                    self._state = CircuitState.OPEN
                    logger.warning(
                        f"Circuit breaker {self.name} opened after {self._failure_count} failures"
                    )

    def _should_attempt_reset(self) -> bool:
        """Check if enough time has passed to attempt recovery."""
        if self._last_failure_time is None:
            return True
        elapsed = (datetime.now(timezone.utc) - self._last_failure_time).total_seconds()
        return elapsed >= self.reset_timeout

    def _reset(self) -> None:
        """Reset circuit to closed state."""
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._last_failure_time = None

    def _is_excluded_exception(self, exc_type: type) -> bool:
        """Check if exception type should be excluded from failure tracking."""
        return issubclass(exc_type, self.exclude_exceptions)

    def get_stats(self) -> dict:
        """Get circuit breaker statistics."""
        return {
            "name": self.name,
            "state": self._state.value,
            "failure_count": self._failure_count,
            "fail_max": self.fail_max,
            "reset_timeout": self.reset_timeout,
            "last_failure_time": (
                self._last_failure_time.isoformat()
                if self._last_failure_time
                else None
            ),
        }


# ===========================================
# Global Circuit Breaker Instances
# ===========================================

_circuit_breakers: dict[str, CircuitBreaker] = {}


def get_circuit_breaker(
    name: str,
    fail_max: Optional[int] = None,
    reset_timeout: Optional[int] = None,
) -> CircuitBreaker:
    """
    Get or create a circuit breaker by name.

    Circuit breakers are reused across calls to maintain state.
    """
    if name not in _circuit_breakers:
        _circuit_breakers[name] = CircuitBreaker(
            name=name,
            fail_max=fail_max,
            reset_timeout=reset_timeout,
        )
    return _circuit_breakers[name]


def get_tavily_breaker() -> CircuitBreaker:
    """Get circuit breaker for Tavily API."""
    return get_circuit_breaker("tavily")


def get_github_breaker() -> CircuitBreaker:
    """Get circuit breaker for GitHub API."""
    return get_circuit_breaker("github")


def get_anthropic_breaker() -> CircuitBreaker:
    """Get circuit breaker for Anthropic API."""
    return get_circuit_breaker("anthropic")


async def get_all_breaker_stats() -> list[dict]:
    """Get stats for all circuit breakers."""
    return [breaker.get_stats() for breaker in _circuit_breakers.values()]
