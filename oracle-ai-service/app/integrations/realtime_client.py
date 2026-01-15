# app/integrations/realtime_client.py
"""
HTTP client for real-time-service API.

Fetches data needed for:
- Analytics computation
- Recommendation generation
- User profile enrichment triggers
"""

import logging
from typing import Any, Optional

import httpx

from app.core.config import settings
from app.core.circuit_breaker import get_circuit_breaker

logger = logging.getLogger(__name__)


class RealtimeServiceClient:
    """
    HTTP client for real-time-service.

    Provides typed methods for fetching:
    - User profiles
    - Connections
    - Recommendations
    - Huddles
    - Follow-ups
    """

    def __init__(
        self,
        base_url: str = "http://real-time-service:3001",
        timeout: float = 30.0,
    ):
        """
        Initialize client.

        Args:
            base_url: Real-time service base URL
            timeout: Request timeout in seconds
        """
        self.base_url = base_url
        self.timeout = timeout
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=self.timeout,
                headers={
                    "Content-Type": "application/json",
                    "X-Service-Name": "oracle-ai-service",
                },
            )
        return self._client

    async def _request(
        self,
        method: str,
        path: str,
        **kwargs,
    ) -> Optional[dict[str, Any]]:
        """Make HTTP request with circuit breaker."""
        breaker = get_circuit_breaker("realtime-service")

        try:
            async with breaker:
                client = await self._get_client()
                response = await client.request(method, path, **kwargs)

                if response.status_code == 404:
                    return None

                response.raise_for_status()
                return response.json()

        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error from real-time-service: {e}")
            raise
        except Exception as e:
            logger.error(f"Error calling real-time-service: {e}")
            raise

    # ===========================================
    # User Profile Methods
    # ===========================================

    async def get_user_profile(self, user_id: str) -> Optional[dict[str, Any]]:
        """Fetch user profile by ID."""
        return await self._request("GET", f"/api/profiles/{user_id}")

    async def get_event_attendees(
        self,
        event_id: str,
        include_profiles: bool = True,
    ) -> list[dict[str, Any]]:
        """
        Fetch all attendees for an event.

        Args:
            event_id: Event identifier
            include_profiles: Whether to include full profile data

        Returns:
            List of attendee data
        """
        params = {"includeProfiles": str(include_profiles).lower()}
        result = await self._request(
            "GET",
            f"/api/events/{event_id}/attendees",
            params=params,
        )
        return result.get("attendees", []) if result else []

    # ===========================================
    # Connection Methods
    # ===========================================

    async def get_event_connections(
        self,
        event_id: str,
    ) -> list[dict[str, Any]]:
        """Fetch all connections for an event."""
        result = await self._request("GET", f"/api/events/{event_id}/connections")
        return result.get("connections", []) if result else []

    async def get_user_connections(
        self,
        user_id: str,
        event_id: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        """Fetch connections for a user."""
        params = {"eventId": event_id} if event_id else {}
        result = await self._request(
            "GET",
            f"/api/users/{user_id}/connections",
            params=params,
        )
        return result.get("connections", []) if result else []

    # ===========================================
    # Recommendation Methods
    # ===========================================

    async def get_event_recommendations(
        self,
        event_id: str,
    ) -> list[dict[str, Any]]:
        """Fetch all recommendations for an event."""
        result = await self._request("GET", f"/api/events/{event_id}/recommendations")
        return result.get("recommendations", []) if result else []

    # ===========================================
    # Huddle Methods
    # ===========================================

    async def get_event_huddles(
        self,
        event_id: str,
    ) -> list[dict[str, Any]]:
        """Fetch all huddles for an event."""
        result = await self._request("GET", f"/api/events/{event_id}/huddles")
        return result.get("huddles", []) if result else []

    async def get_huddle_invites(
        self,
        event_id: str,
    ) -> list[dict[str, Any]]:
        """Fetch all huddle invitations for an event."""
        result = await self._request("GET", f"/api/events/{event_id}/huddle-invites")
        return result.get("invites", []) if result else []

    # ===========================================
    # Follow-up Methods
    # ===========================================

    async def get_event_follow_ups(
        self,
        event_id: str,
    ) -> list[dict[str, Any]]:
        """Fetch all follow-ups for an event."""
        result = await self._request("GET", f"/api/events/{event_id}/follow-ups")
        return result.get("followUps", []) if result else []

    # ===========================================
    # Ping/DM Methods
    # ===========================================

    async def get_event_pings(
        self,
        event_id: str,
    ) -> list[dict[str, Any]]:
        """Fetch all pings for an event."""
        result = await self._request("GET", f"/api/events/{event_id}/pings")
        return result.get("pings", []) if result else []

    async def get_event_dms(
        self,
        event_id: str,
    ) -> list[dict[str, Any]]:
        """Fetch all direct messages for an event."""
        result = await self._request("GET", f"/api/events/{event_id}/dms")
        return result.get("dms", []) if result else []

    # ===========================================
    # Lifecycle
    # ===========================================

    async def close(self) -> None:
        """Close HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None


# Singleton instance
_client: Optional[RealtimeServiceClient] = None


async def get_realtime_client() -> RealtimeServiceClient:
    """Get or create realtime service client singleton."""
    global _client
    if _client is None:
        _client = RealtimeServiceClient()
    return _client
