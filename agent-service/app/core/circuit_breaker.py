"""
Circuit Breaker Pattern Implementation

Provides resilience for external service calls (Redis, Database, LLM APIs).
Prevents cascade failures by failing fast when services are unhealthy.

States:
- CLOSED: Normal operation, requests pass through
- OPEN: Service is failing, requests fail immediately
- HALF_OPEN: Testing if service has recovered

Usage:
    @circuit_breaker(name="redis", failure_threshold=5, recovery_timeout=30)
    async def call_redis():
        ...

    # Or use the CircuitBreaker class directly:
    breaker = CircuitBreaker(name="llm", failure_threshold=3, recovery_timeout=60)
    async with breaker:
        await call_llm()
"""

import asyncio
import time
import logging
from typing import Optional, Callable, Any, Dict
from dataclasses import dataclass, field
from enum import Enum
from functools import wraps
from datetime import datetime, timezone
import threading

logger = logging.getLogger(__name__)


class CircuitState(str, Enum):
    """Circuit breaker states"""
    CLOSED = "CLOSED"       # Normal operation
    OPEN = "OPEN"           # Failing fast
    HALF_OPEN = "HALF_OPEN" # Testing recovery


@dataclass
class CircuitBreakerStats:
    """Statistics for a circuit breaker"""
    name: str
    state: CircuitState = CircuitState.CLOSED
    failure_count: int = 0
    success_count: int = 0
    last_failure_time: Optional[float] = None
    last_success_time: Optional[float] = None
    total_requests: int = 0
    total_failures: int = 0
    total_circuit_opens: int = 0

    def to_dict(self) -> Dict:
        return {
            "name": self.name,
            "state": self.state.value,
            "failure_count": self.failure_count,
            "success_count": self.success_count,
            "last_failure_time": self.last_failure_time,
            "last_success_time": self.last_success_time,
            "total_requests": self.total_requests,
            "total_failures": self.total_failures,
            "total_circuit_opens": self.total_circuit_opens,
            "failure_rate": self.failure_rate,
        }

    @property
    def failure_rate(self) -> float:
        if self.total_requests == 0:
            return 0.0
        return self.total_failures / self.total_requests


class CircuitBreakerError(Exception):
    """Raised when circuit breaker is open"""
    def __init__(self, name: str, message: str = "Circuit breaker is open"):
        self.name = name
        self.message = f"[{name}] {message}"
        super().__init__(self.message)


class CircuitBreaker:
    """
    Circuit breaker for external service calls.

    Attributes:
        name: Identifier for this circuit breaker
        failure_threshold: Number of failures before opening circuit
        recovery_timeout: Seconds to wait before trying again (half-open state)
        success_threshold: Number of successes in half-open before closing
        expected_exceptions: Exception types that count as failures
    """

    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        recovery_timeout: float = 30.0,
        success_threshold: int = 2,
        expected_exceptions: tuple = (Exception,),
    ):
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.success_threshold = success_threshold
        self.expected_exceptions = expected_exceptions

        self._stats = CircuitBreakerStats(name=name)
        self._lock = threading.Lock()

        logger.info(
            f"Circuit breaker '{name}' initialized: "
            f"failure_threshold={failure_threshold}, "
            f"recovery_timeout={recovery_timeout}s"
        )

    @property
    def state(self) -> CircuitState:
        return self._stats.state

    @property
    def stats(self) -> CircuitBreakerStats:
        return self._stats

    def _should_allow_request(self) -> bool:
        """Determine if a request should be allowed through."""
        with self._lock:
            if self._stats.state == CircuitState.CLOSED:
                return True

            if self._stats.state == CircuitState.OPEN:
                # Check if recovery timeout has passed
                if self._stats.last_failure_time:
                    elapsed = time.time() - self._stats.last_failure_time
                    if elapsed >= self.recovery_timeout:
                        # Transition to half-open
                        self._stats.state = CircuitState.HALF_OPEN
                        self._stats.failure_count = 0
                        self._stats.success_count = 0
                        logger.info(
                            f"Circuit breaker '{self.name}' transitioning to HALF_OPEN "
                            f"after {elapsed:.1f}s"
                        )
                        return True
                return False

            # HALF_OPEN - allow limited requests
            return True

    def _record_success(self):
        """Record a successful call."""
        with self._lock:
            self._stats.success_count += 1
            self._stats.total_requests += 1
            self._stats.last_success_time = time.time()

            if self._stats.state == CircuitState.HALF_OPEN:
                if self._stats.success_count >= self.success_threshold:
                    # Close the circuit
                    self._stats.state = CircuitState.CLOSED
                    self._stats.failure_count = 0
                    logger.info(
                        f"Circuit breaker '{self.name}' CLOSED after "
                        f"{self._stats.success_count} successful calls"
                    )

    def _record_failure(self, exception: Exception):
        """Record a failed call."""
        with self._lock:
            self._stats.failure_count += 1
            self._stats.total_failures += 1
            self._stats.total_requests += 1
            self._stats.last_failure_time = time.time()

            if self._stats.state == CircuitState.HALF_OPEN:
                # Any failure in half-open reopens the circuit
                self._stats.state = CircuitState.OPEN
                self._stats.total_circuit_opens += 1
                logger.warning(
                    f"Circuit breaker '{self.name}' re-OPENED after failure in HALF_OPEN: {exception}"
                )

            elif self._stats.state == CircuitState.CLOSED:
                if self._stats.failure_count >= self.failure_threshold:
                    # Open the circuit
                    self._stats.state = CircuitState.OPEN
                    self._stats.total_circuit_opens += 1
                    logger.warning(
                        f"Circuit breaker '{self.name}' OPENED after "
                        f"{self._stats.failure_count} failures"
                    )

    async def __aenter__(self):
        """Async context manager entry."""
        if not self._should_allow_request():
            raise CircuitBreakerError(
                self.name,
                f"Circuit is OPEN. Will retry after {self.recovery_timeout}s"
            )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if exc_val is None:
            self._record_success()
        elif isinstance(exc_val, self.expected_exceptions):
            self._record_failure(exc_val)
        return False  # Don't suppress exceptions

    def __enter__(self):
        """Sync context manager entry."""
        if not self._should_allow_request():
            raise CircuitBreakerError(
                self.name,
                f"Circuit is OPEN. Will retry after {self.recovery_timeout}s"
            )
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Sync context manager exit."""
        if exc_val is None:
            self._record_success()
        elif isinstance(exc_val, self.expected_exceptions):
            self._record_failure(exc_val)
        return False

    def call(self, func: Callable, *args, **kwargs) -> Any:
        """Execute a function with circuit breaker protection (sync)."""
        with self:
            return func(*args, **kwargs)

    async def call_async(self, func: Callable, *args, **kwargs) -> Any:
        """Execute an async function with circuit breaker protection."""
        async with self:
            return await func(*args, **kwargs)

    def reset(self):
        """Manually reset the circuit breaker to closed state."""
        with self._lock:
            self._stats.state = CircuitState.CLOSED
            self._stats.failure_count = 0
            self._stats.success_count = 0
            logger.info(f"Circuit breaker '{self.name}' manually reset to CLOSED")


# Global circuit breaker registry
_circuit_breakers: Dict[str, CircuitBreaker] = {}
_registry_lock = threading.Lock()


def get_circuit_breaker(
    name: str,
    failure_threshold: int = 5,
    recovery_timeout: float = 30.0,
    success_threshold: int = 2,
    expected_exceptions: tuple = (Exception,),
) -> CircuitBreaker:
    """
    Get or create a circuit breaker by name.

    This ensures only one circuit breaker exists per name (singleton pattern).
    """
    with _registry_lock:
        if name not in _circuit_breakers:
            _circuit_breakers[name] = CircuitBreaker(
                name=name,
                failure_threshold=failure_threshold,
                recovery_timeout=recovery_timeout,
                success_threshold=success_threshold,
                expected_exceptions=expected_exceptions,
            )
        return _circuit_breakers[name]


def circuit_breaker(
    name: str,
    failure_threshold: int = 5,
    recovery_timeout: float = 30.0,
    success_threshold: int = 2,
    expected_exceptions: tuple = (Exception,),
):
    """
    Decorator to wrap a function with circuit breaker protection.

    Usage:
        @circuit_breaker(name="redis", failure_threshold=5, recovery_timeout=30)
        async def call_redis():
            ...
    """
    def decorator(func: Callable):
        breaker = get_circuit_breaker(
            name=name,
            failure_threshold=failure_threshold,
            recovery_timeout=recovery_timeout,
            success_threshold=success_threshold,
            expected_exceptions=expected_exceptions,
        )

        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            return await breaker.call_async(func, *args, **kwargs)

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            return breaker.call(func, *args, **kwargs)

        # Return appropriate wrapper based on function type
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator


def get_all_circuit_breaker_stats() -> Dict[str, Dict]:
    """Get statistics for all circuit breakers."""
    with _registry_lock:
        return {name: cb.stats.to_dict() for name, cb in _circuit_breakers.items()}


def reset_all_circuit_breakers():
    """Reset all circuit breakers to closed state."""
    with _registry_lock:
        for cb in _circuit_breakers.values():
            cb.reset()


# Pre-configured circuit breakers for common services
redis_circuit_breaker = get_circuit_breaker(
    name="redis",
    failure_threshold=5,
    recovery_timeout=30.0,
    expected_exceptions=(Exception,),
)

database_circuit_breaker = get_circuit_breaker(
    name="database",
    failure_threshold=5,
    recovery_timeout=30.0,
    expected_exceptions=(Exception,),
)

llm_circuit_breaker = get_circuit_breaker(
    name="llm",
    failure_threshold=3,
    recovery_timeout=60.0,  # Longer timeout for LLM services
    expected_exceptions=(Exception,),
)
