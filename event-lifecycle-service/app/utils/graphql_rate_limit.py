# app/utils/graphql_rate_limit.py
"""
Rate limiting utilities for GraphQL mutations.

Provides decorators to prevent abuse of GraphQL mutations by limiting
the number of requests per user within a time window.
"""

import inspect
import time
import functools
import logging
from typing import Callable, Dict, Tuple
from collections import defaultdict
from threading import Lock
from fastapi import HTTPException

logger = logging.getLogger(__name__)

# In-memory storage for rate limits (user_id -> (request_count, window_start))
# In production, consider using Redis for distributed rate limiting
_rate_limit_store: Dict[str, Dict[str, Tuple[int, float]]] = defaultdict(dict)
_store_lock = Lock()


def rate_limit(max_calls: int, period_seconds: int):
    """
    Decorator to rate limit GraphQL mutations.

    Args:
        max_calls: Maximum number of calls allowed within the period
        period_seconds: Time period in seconds

    Example:
        @rate_limit(max_calls=5, period_seconds=60)  # 5 calls per minute
        def rsvp_to_session(self, input, info):
            ...

    Raises:
        HTTPException: When rate limit is exceeded
    """
    def _check_rate_limit(operation_name: str, args, kwargs):
        """Shared rate limit check logic. Raises HTTPException if limit exceeded."""
        # Extract user from info.context
        info = kwargs.get('info') or (args[2] if len(args) > 2 else None)
        if not info or not info.context or not info.context.user:
            return
        user_id = info.context.user.get('sub')
        if not user_id:
            return

        current_time = time.time()
        key = f"{operation_name}:{user_id}"

        with _store_lock:
            if key in _rate_limit_store:
                count, window_start = _rate_limit_store[key]

                # Check if we're still within the rate limit window
                if current_time - window_start < period_seconds:
                    if count >= max_calls:
                        # Rate limit exceeded
                        reset_time = int(window_start + period_seconds - current_time)
                        logger.warning(
                            f"Rate limit exceeded for user {user_id} on {operation_name}. "
                            f"Limit: {max_calls}/{period_seconds}s"
                        )
                        raise HTTPException(
                            status_code=429,
                            detail=f"Rate limit exceeded. Try again in {reset_time} seconds."
                        )

                    # Increment count within current window
                    _rate_limit_store[key] = (count + 1, window_start)
                else:
                    # Window expired - start new window
                    _rate_limit_store[key] = (1, current_time)
            else:
                # First request for this user+operation
                _rate_limit_store[key] = (1, current_time)

    def decorator(func: Callable):
        operation_name = func.__name__

        if inspect.iscoroutinefunction(func):
            @functools.wraps(func)
            async def async_wrapper(*args, **kwargs):
                _check_rate_limit(operation_name, args, kwargs)
                return await func(*args, **kwargs)
            return async_wrapper
        else:
            @functools.wraps(func)
            def wrapper(*args, **kwargs):
                _check_rate_limit(operation_name, args, kwargs)
                return func(*args, **kwargs)
            return wrapper

    return decorator


def cleanup_expired_entries():
    """
    Cleanup expired rate limit entries to prevent memory leaks.
    Should be called periodically (e.g., via background task).
    """
    current_time = time.time()
    max_window = 3600  # 1 hour - assume no rate limit window is longer than this

    with _store_lock:
        expired_keys = [
            key for key, (_, window_start) in _rate_limit_store.items()
            if current_time - window_start > max_window
        ]

        for key in expired_keys:
            del _rate_limit_store[key]

        if expired_keys:
            logger.info(f"Cleaned up {len(expired_keys)} expired rate limit entries")
