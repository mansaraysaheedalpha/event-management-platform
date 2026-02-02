"""
Rate Limiter Implementation

Provides rate limiting for interventions and API calls to prevent:
- Overwhelming users with too many interventions
- API abuse
- System overload during anomaly storms

Uses a sliding window algorithm for accurate rate limiting.

Usage:
    limiter = RateLimiter(max_requests=1, window_seconds=30)
    if await limiter.is_allowed("session_123"):
        # proceed with intervention
    else:
        # rate limited
"""

import asyncio
import time
import logging
from typing import Dict, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timezone
from collections import deque
import threading

logger = logging.getLogger(__name__)


@dataclass
class RateLimiterStats:
    """Statistics for rate limiter"""
    name: str
    total_requests: int = 0
    total_allowed: int = 0
    total_rejected: int = 0

    @property
    def rejection_rate(self) -> float:
        if self.total_requests == 0:
            return 0.0
        return self.total_rejected / self.total_requests

    def to_dict(self) -> Dict:
        return {
            "name": self.name,
            "total_requests": self.total_requests,
            "total_allowed": self.total_allowed,
            "total_rejected": self.total_rejected,
            "rejection_rate": self.rejection_rate,
        }


class RateLimiter:
    """
    Sliding window rate limiter.

    Attributes:
        name: Identifier for this rate limiter
        max_requests: Maximum requests allowed per window
        window_seconds: Window size in seconds
        cleanup_interval: How often to clean up old entries (seconds)
    """

    def __init__(
        self,
        name: str,
        max_requests: int = 1,
        window_seconds: float = 30.0,
        cleanup_interval: float = 60.0,
    ):
        self.name = name
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.cleanup_interval = cleanup_interval

        # Sliding window for each key: {key: deque of timestamps}
        self._windows: Dict[str, deque] = {}
        self._lock = threading.Lock()
        self._stats = RateLimiterStats(name=name)

        # Background cleanup
        self._cleanup_task: Optional[asyncio.Task] = None

        logger.info(
            f"Rate limiter '{name}' initialized: "
            f"max_requests={max_requests}, window_seconds={window_seconds}s"
        )

    @property
    def stats(self) -> RateLimiterStats:
        return self._stats

    def is_allowed_sync(self, key: str) -> bool:
        """
        Check if a request is allowed (synchronous version).

        Args:
            key: Unique identifier (e.g., session_id)

        Returns:
            True if request is allowed, False if rate limited
        """
        with self._lock:
            self._stats.total_requests += 1
            now = time.time()
            cutoff = now - self.window_seconds

            # Get or create window for this key
            if key not in self._windows:
                self._windows[key] = deque()

            window = self._windows[key]

            # Remove expired entries
            while window and window[0] < cutoff:
                window.popleft()

            # Check if under limit
            if len(window) < self.max_requests:
                window.append(now)
                self._stats.total_allowed += 1
                return True
            else:
                self._stats.total_rejected += 1
                logger.debug(
                    f"Rate limited key '{key}' in limiter '{self.name}': "
                    f"{len(window)}/{self.max_requests} requests in window"
                )
                return False

    async def is_allowed(self, key: str) -> bool:
        """
        Check if a request is allowed (async version).

        Args:
            key: Unique identifier (e.g., session_id)

        Returns:
            True if request is allowed, False if rate limited
        """
        # Run sync version in thread pool to avoid blocking (Python 3.9+)
        return await asyncio.to_thread(self.is_allowed_sync, key)

    def get_current_count_sync(self, key: str) -> int:
        """
        Get the current count of requests in the window (sync version).

        Args:
            key: Unique identifier

        Returns:
            Number of requests in current window
        """
        with self._lock:
            now = time.time()
            cutoff = now - self.window_seconds

            if key not in self._windows:
                return 0

            window = self._windows[key]

            # Remove expired entries
            while window and window[0] < cutoff:
                window.popleft()

            return len(window)

    async def get_current_count(self, key: str) -> int:
        """
        Get the current count of requests in the window (async version).

        Args:
            key: Unique identifier

        Returns:
            Number of requests in current window
        """
        return await asyncio.to_thread(self.get_current_count_sync, key)

    def get_wait_time(self, key: str) -> float:
        """
        Get the time to wait before the next request is allowed.

        Args:
            key: Unique identifier

        Returns:
            Seconds to wait (0 if immediately allowed)
        """
        with self._lock:
            if key not in self._windows:
                return 0.0

            window = self._windows[key]
            if len(window) < self.max_requests:
                return 0.0

            # Calculate time until oldest request expires
            oldest = window[0]
            now = time.time()
            wait_time = (oldest + self.window_seconds) - now
            return max(0.0, wait_time)

    async def wait_and_acquire(self, key: str, timeout: float = 60.0) -> bool:
        """
        Wait until rate limit allows, then acquire.

        Args:
            key: Unique identifier
            timeout: Maximum time to wait

        Returns:
            True if acquired, False if timeout
        """
        start = time.time()
        while (time.time() - start) < timeout:
            if await self.is_allowed(key):
                return True
            wait_time = min(self.get_wait_time(key), timeout - (time.time() - start))
            if wait_time > 0:
                await asyncio.sleep(wait_time)
        return False

    def reset(self, key: Optional[str] = None):
        """
        Reset rate limiter state.

        Args:
            key: Specific key to reset, or None to reset all
        """
        with self._lock:
            if key:
                if key in self._windows:
                    del self._windows[key]
            else:
                self._windows.clear()

    async def start_cleanup_task(self):
        """Start background cleanup of expired windows."""
        if self._cleanup_task is None or self._cleanup_task.done():
            self._cleanup_task = asyncio.create_task(self._cleanup_loop())

    async def stop_cleanup_task(self):
        """Stop background cleanup task."""
        if self._cleanup_task and not self._cleanup_task.done():
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass

    async def _cleanup_loop(self):
        """Background cleanup of expired windows."""
        while True:
            try:
                await asyncio.sleep(self.cleanup_interval)
                self._cleanup_expired()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in rate limiter cleanup: {e}")

    def _cleanup_expired(self):
        """Remove keys with empty windows."""
        with self._lock:
            now = time.time()
            cutoff = now - self.window_seconds
            empty_keys = []

            for key, window in self._windows.items():
                # Remove expired entries
                while window and window[0] < cutoff:
                    window.popleft()
                # Mark empty windows for removal
                if not window:
                    empty_keys.append(key)

            for key in empty_keys:
                del self._windows[key]

            if empty_keys:
                logger.debug(f"Rate limiter '{self.name}' cleaned up {len(empty_keys)} expired keys")


class SessionInterventionRateLimiter:
    """
    Specialized rate limiter for session interventions.

    Enforces limits like:
    - Max 1 intervention per 30 seconds per session
    - Max 10 interventions per 5 minutes per session
    - Max 100 interventions per hour per event
    """

    def __init__(self):
        # Short-term limit: 1 intervention per 30 seconds per session
        self.short_term = RateLimiter(
            name="intervention_short_term",
            max_requests=1,
            window_seconds=30.0,
        )

        # Medium-term limit: 10 interventions per 5 minutes per session
        self.medium_term = RateLimiter(
            name="intervention_medium_term",
            max_requests=10,
            window_seconds=300.0,  # 5 minutes
        )

        # Long-term limit: 100 interventions per hour per event
        self.long_term = RateLimiter(
            name="intervention_long_term",
            max_requests=100,
            window_seconds=3600.0,  # 1 hour
        )

    async def is_intervention_allowed(
        self,
        session_id: str,
        event_id: str,
        max_per_hour: Optional[int] = None
    ) -> Tuple[bool, Optional[str]]:
        """
        Check if an intervention is allowed for a session.

        Args:
            session_id: Session identifier
            event_id: Event identifier
            max_per_hour: Optional per-event limit from EventAgentSettings.
                          If provided and stricter than global limit (100), applies instead.

        Returns:
            Tuple of (allowed: bool, rejection_reason: Optional[str])
        """
        # Check short-term limit
        if not await self.short_term.is_allowed(session_id):
            return False, "Rate limit: Max 1 intervention per 30 seconds"

        # Check medium-term limit
        if not await self.medium_term.is_allowed(session_id):
            return False, "Rate limit: Max 10 interventions per 5 minutes"

        # Check long-term limit (per event)
        # Use per-event limit if provided and stricter than global default
        effective_limit = self.long_term.max_requests  # Default: 100
        if max_per_hour is not None and max_per_hour < effective_limit:
            # Check custom per-event limit
            event_key = f"{event_id}:custom"
            current_count = await self._get_hourly_count(event_id)
            if current_count >= max_per_hour:
                return False, f"Rate limit: Max {max_per_hour} interventions per hour for this event"

        # Always check global limit
        if not await self.long_term.is_allowed(event_id):
            return False, "Rate limit: Max 100 interventions per hour for this event"

        return True, None

    async def _get_hourly_count(self, event_id: str) -> int:
        """Get the current count of interventions in the last hour for an event."""
        # Use the long_term limiter's window to count
        return await self.long_term.get_current_count(event_id)

    def get_stats(self) -> Dict:
        """Get stats for all limiters."""
        return {
            "short_term": self.short_term.stats.to_dict(),
            "medium_term": self.medium_term.stats.to_dict(),
            "long_term": self.long_term.stats.to_dict(),
        }


# Global intervention rate limiter instance
_intervention_rate_limiter: Optional[SessionInterventionRateLimiter] = None


def get_intervention_rate_limiter() -> SessionInterventionRateLimiter:
    """Get or create the global intervention rate limiter."""
    global _intervention_rate_limiter
    if _intervention_rate_limiter is None:
        _intervention_rate_limiter = SessionInterventionRateLimiter()
    return _intervention_rate_limiter
