# app/features/enrichment/service.py
"""
Business logic for profile enrichment feature.
"""

import logging
from typing import Any, Optional

from app.agents.profile_enrichment import (
    EnrichmentInput,
    EnrichmentResult,
    EnrichmentStatus,
    ProfileTier,
    run_enrichment,
)
from app.agents.profile_enrichment.fallback import EnrichmentFallbackHandler
from app.core.config import settings
from app.core.exceptions import (
    EnrichmentAlreadyProcessingError,
    EnrichmentDisabledError,
    EnrichmentOptedOutError,
    UserRateLimitError,
)
from app.core.rate_limiter import get_user_enrichment_limiter
from app.tasks.enrichment_tasks import enrich_user_task, queue_event_enrichments

logger = logging.getLogger(__name__)


class EnrichmentService:
    """
    Service for managing profile enrichment.

    Provides:
    - On-demand enrichment (async background processing)
    - Sync enrichment (for testing/debugging)
    - Batch enrichment for events
    - Status checking and statistics
    """

    def __init__(self):
        """Initialize enrichment service."""
        self.fallback_handler = EnrichmentFallbackHandler()

    async def enrich_user_async(
        self,
        user_id: str,
        name: str,
        email: str,
        company: str,
        role: str,
        linkedin_url: Optional[str] = None,
        github_username: Optional[str] = None,
        twitter_handle: Optional[str] = None,
        current_status: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        Queue user for background enrichment.

        Args:
            user_id: User identifier
            name: User's full name
            email: User's email
            company: User's company
            role: User's job role
            linkedin_url: Optional LinkedIn URL
            github_username: Optional GitHub username
            twitter_handle: Optional Twitter handle
            current_status: Current enrichment status (if known)

        Returns:
            Dict with status and task info

        Raises:
            EnrichmentDisabledError: If enrichment not configured
            EnrichmentOptedOutError: If user opted out
            EnrichmentAlreadyProcessingError: If enrichment in progress
            UserRateLimitError: If user rate limit exceeded
        """
        # Check if enrichment is enabled
        if not settings.enrichment_enabled:
            raise EnrichmentDisabledError()

        # Check current status
        if current_status == EnrichmentStatus.OPTED_OUT.value:
            raise EnrichmentOptedOutError(user_id)

        if current_status == EnrichmentStatus.PROCESSING.value:
            raise EnrichmentAlreadyProcessingError(user_id)

        if current_status == EnrichmentStatus.COMPLETED.value:
            return {
                "status": "already_enriched",
                "message": "Profile already enriched",
            }

        # Check per-user rate limit
        limiter = await get_user_enrichment_limiter()
        await limiter.acquire(user_id)

        # Queue background task
        task = enrich_user_task.delay(
            user_id=user_id,
            name=name,
            email=email,
            company=company,
            role=role,
            linkedin_url=linkedin_url,
            github_username=github_username,
            twitter_handle=twitter_handle,
        )

        logger.info(f"Queued enrichment task {task.id} for user {user_id}")

        return {
            "status": "processing",
            "message": "Enrichment started in background",
            "task_id": task.id,
        }

    async def enrich_user_sync(
        self,
        user_id: str,
        name: str,
        email: str,
        company: str,
        role: str,
        linkedin_url: Optional[str] = None,
        github_username: Optional[str] = None,
        twitter_handle: Optional[str] = None,
    ) -> EnrichmentResult:
        """
        Run enrichment synchronously (for testing/debugging).

        WARNING: This blocks the request. Use async version in production.

        Args:
            user_id: User identifier
            name: User's full name
            email: User's email
            company: User's company
            role: User's job role
            linkedin_url: Optional LinkedIn URL
            github_username: Optional GitHub username
            twitter_handle: Optional Twitter handle

        Returns:
            Enrichment result
        """
        if not settings.enrichment_enabled:
            raise EnrichmentDisabledError()

        # Check per-user rate limit
        limiter = await get_user_enrichment_limiter()
        await limiter.acquire(user_id)

        # Create input
        input_data = EnrichmentInput(
            user_id=user_id,
            name=name,
            email=email,
            company=company,
            role=role,
            linkedin_url=linkedin_url,
            github_username=github_username,
            twitter_handle=twitter_handle,
        )

        # Run enrichment
        result = await run_enrichment(input_data)

        # Handle fallback logic
        await self.fallback_handler.handle_enrichment_result(user_id, result)

        return result

    async def enrich_event_attendees(
        self,
        event_id: str,
        attendees: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """
        Queue all attendees for enrichment.

        Spreads enrichments over time to avoid API spikes.

        Args:
            event_id: Event identifier
            attendees: List of attendee data dicts

        Returns:
            Summary of queued tasks
        """
        if not settings.enrichment_enabled:
            raise EnrichmentDisabledError()

        # Queue batch task
        task = queue_event_enrichments.delay(
            event_id=event_id,
            attendees=attendees,
        )

        logger.info(f"Queued batch enrichment task {task.id} for event {event_id}")

        return {
            "event_id": event_id,
            "status": "queued",
            "message": f"Enrichment queued for {len(attendees)} attendees",
            "task_id": task.id,
        }

    def get_enrichment_status(
        self,
        user_id: str,
        # These would come from database lookup
        status: Optional[str] = None,
        tier: Optional[str] = None,
        enriched_at: Optional[str] = None,
        sources: Optional[list[str]] = None,
    ) -> dict[str, Any]:
        """
        Get enrichment status for a user.

        Args:
            user_id: User identifier
            status: Current status from database
            tier: Current tier from database
            enriched_at: Enrichment timestamp from database
            sources: Sources found from database

        Returns:
            Status information dict
        """
        return {
            "user_id": user_id,
            "status": status or EnrichmentStatus.PENDING.value,
            "profile_tier": tier or ProfileTier.TIER_0_PENDING.value,
            "enriched_at": enriched_at,
            "sources": sources or [],
        }


# Singleton service instance
_service: Optional[EnrichmentService] = None


def get_enrichment_service() -> EnrichmentService:
    """Get or create enrichment service singleton."""
    global _service
    if _service is None:
        _service = EnrichmentService()
    return _service
