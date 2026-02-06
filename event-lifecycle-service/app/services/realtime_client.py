"""
Client for calling real-time-service APIs for recommendations.

Uses synchronous httpx for background task compatibility.
Implements circuit breaker pattern for resilience.
"""

import logging
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

# Circuit breaker state for real-time service calls
_circuit_breaker = {
    "failures": 0,
    "last_failure": None,
    "threshold": 5,
    "reset_timeout": 60,  # seconds
}


def _circuit_breaker_open() -> bool:
    """Check if circuit breaker is open (should not call external service)."""
    if _circuit_breaker["failures"] < _circuit_breaker["threshold"]:
        return False

    if _circuit_breaker["last_failure"] is None:
        return False

    elapsed = (datetime.now(timezone.utc) - _circuit_breaker["last_failure"]).seconds
    if elapsed > _circuit_breaker["reset_timeout"]:
        # Reset circuit breaker
        _circuit_breaker["failures"] = 0
        _circuit_breaker["last_failure"] = None
        logger.info("Circuit breaker reset after timeout")
        return False

    return True


def _record_circuit_failure():
    """Record a failure for circuit breaker."""
    _circuit_breaker["failures"] += 1
    _circuit_breaker["last_failure"] = datetime.now(timezone.utc)
    logger.warning(
        f"Circuit breaker failure recorded: {_circuit_breaker['failures']}/{_circuit_breaker['threshold']}"
    )


def _record_circuit_success():
    """Record a success (reset failure count)."""
    _circuit_breaker["failures"] = 0


class RealTimeServiceClient:
    """
    Synchronous client for real-time-service internal API.

    Used by background tasks to fetch recommendations for pre-event emails.
    """

    def __init__(self):
        self.base_url = settings.REAL_TIME_SERVICE_URL_INTERNAL
        self.api_key = settings.INTERNAL_API_KEY
        self.timeout = 30.0

    def get_recommendations_for_user(
        self,
        user_id: str,
        event_id: str,
        limit: int = 5,
    ) -> List[Dict[str, Any]]:
        """
        Get personalized networking recommendations for a user.

        Calls: GET /events/{eventId}/recommendations?userId={userId}&limit={limit}

        Args:
            user_id: The user ID to get recommendations for
            event_id: The event ID
            limit: Maximum number of recommendations to return

        Returns:
            List of recommendation objects with user info and match scores
        """
        if _circuit_breaker_open():
            logger.warning("Circuit breaker open, returning empty recommendations")
            return []

        if not self.base_url:
            logger.warning("REAL_TIME_SERVICE_URL_INTERNAL not configured")
            return []

        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.get(
                    f"{self.base_url}/events/{event_id}/recommendations",
                    params={
                        "userId": user_id,
                        "limit": limit,
                    },
                    headers={
                        "X-API-Key": self.api_key,
                        "Content-Type": "application/json",
                    },
                )

                if response.status_code == 200:
                    _record_circuit_success()
                    data = response.json()
                    recommendations = data.get("recommendations", [])
                    logger.debug(
                        f"Got {len(recommendations)} recommendations for user {user_id}"
                    )
                    return recommendations
                else:
                    logger.warning(
                        f"Recommendations API returned {response.status_code}: {response.text}"
                    )
                    _record_circuit_failure()
                    return []

        except httpx.TimeoutException:
            logger.warning("Recommendations API timeout")
            _record_circuit_failure()
            return []
        except httpx.RequestError as e:
            logger.warning(f"Recommendations API request error: {e}")
            _record_circuit_failure()
            return []
        except Exception as e:
            logger.error(f"Unexpected error calling recommendations API: {e}")
            _record_circuit_failure()
            return []

    def get_session_recommendations(
        self,
        user_id: str,
        event_id: str,
        limit: int = 5,
    ) -> List[Dict[str, Any]]:
        """
        Get personalized session recommendations for a user.

        Note: This endpoint may not exist yet in real-time-service.
        Falls back to empty list if not available.

        Args:
            user_id: The user ID to get recommendations for
            event_id: The event ID
            limit: Maximum number of sessions to recommend

        Returns:
            List of session recommendation objects
        """
        if _circuit_breaker_open():
            return []

        if not self.base_url:
            return []

        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.get(
                    f"{self.base_url}/events/{event_id}/sessions/recommendations",
                    params={
                        "userId": user_id,
                        "limit": limit,
                    },
                    headers={
                        "X-API-Key": self.api_key,
                        "Content-Type": "application/json",
                    },
                )

                if response.status_code == 200:
                    _record_circuit_success()
                    data = response.json()
                    return data.get("sessions", [])
                elif response.status_code == 404:
                    # Endpoint not implemented yet
                    logger.debug("Session recommendations endpoint not available")
                    return []
                else:
                    logger.warning(
                        f"Session recommendations API returned {response.status_code}"
                    )
                    _record_circuit_failure()
                    return []

        except Exception as e:
            logger.warning(f"Error getting session recommendations: {e}")
            return []

    def get_circuit_breaker_status(self) -> dict:
        """Get current circuit breaker status for monitoring."""
        return {
            "failures": _circuit_breaker["failures"],
            "threshold": _circuit_breaker["threshold"],
            "is_open": _circuit_breaker_open(),
            "last_failure": (
                _circuit_breaker["last_failure"].isoformat()
                if _circuit_breaker["last_failure"]
                else None
            ),
        }


# Singleton instance
realtime_client = RealTimeServiceClient()
