# app/agents/profile_enrichment/fallback.py
"""
Enrichment failure handling and profile tier management.

Handles graceful degradation when enrichment fails and prompts
users to complete their profiles manually.
"""

import logging
from datetime import datetime, timezone
from typing import Any, Optional

from app.agents.profile_enrichment.schemas import (
    EnrichmentResult,
    EnrichmentStatus,
    ProfileTier,
)

logger = logging.getLogger(__name__)


class EnrichmentFallbackHandler:
    """
    Handles enrichment failures gracefully.

    Target: 60%+ success rate for enrichment.
    For failed enrichments, prompts users to add data manually.
    """

    def __init__(self, notification_service: Optional[Any] = None):
        """
        Initialize fallback handler.

        Args:
            notification_service: Optional service for sending user notifications
        """
        self.notification_service = notification_service

    async def handle_enrichment_result(
        self,
        user_id: str,
        result: EnrichmentResult,
    ) -> ProfileTier:
        """
        Process enrichment result and determine profile tier.

        Args:
            user_id: User identifier
            result: Enrichment result from agent

        Returns:
            Assigned profile tier
        """
        sources_count = len(result.sources_found)

        if sources_count >= 3:
            tier = ProfileTier.TIER_1_RICH
            await self._mark_as_enriched(user_id, tier, result)
            logger.info(f"User {user_id} assigned TIER_1_RICH ({sources_count} sources)")

        elif sources_count >= 1:
            tier = ProfileTier.TIER_2_BASIC
            await self._mark_as_enriched(user_id, tier, result)
            await self._send_completion_prompt(user_id, result.missing_sources)
            logger.info(f"User {user_id} assigned TIER_2_BASIC ({sources_count} sources)")

        else:
            tier = ProfileTier.TIER_3_MANUAL
            await self._mark_enrichment_failed(user_id, result.error)
            await self._send_manual_input_request(user_id)
            logger.info(f"User {user_id} assigned TIER_3_MANUAL (no sources found)")

        return tier

    async def _mark_as_enriched(
        self,
        user_id: str,
        tier: ProfileTier,
        result: EnrichmentResult,
    ) -> None:
        """
        Mark user profile as enriched in database.

        Args:
            user_id: User identifier
            tier: Assigned profile tier
            result: Enrichment result
        """
        # This would update the database - stubbed for now
        # In production, this would call the database service
        logger.debug(
            f"Marking user {user_id} as enriched with tier {tier.value}, "
            f"sources: {result.sources_found}"
        )

        # Example database update:
        # await prisma.userprofile.update(
        #     where={"userId": user_id},
        #     data={
        #         "enrichmentStatus": EnrichmentStatus.COMPLETED.value,
        #         "enrichedAt": datetime.now(timezone.utc),
        #         "profileTier": tier.value,
        #         "linkedInUrl": result.enriched_profile.linkedin_url if result.enriched_profile else None,
        #         # ... other fields
        #     }
        # )

    async def _mark_enrichment_failed(
        self,
        user_id: str,
        error: Optional[str] = None,
    ) -> None:
        """
        Mark enrichment as failed in database.

        Args:
            user_id: User identifier
            error: Error message if any
        """
        logger.debug(f"Marking enrichment failed for user {user_id}: {error}")

        # Example database update:
        # await prisma.userprofile.update(
        #     where={"userId": user_id},
        #     data={
        #         "enrichmentStatus": EnrichmentStatus.FAILED.value,
        #         "profileTier": ProfileTier.TIER_3_MANUAL.value,
        #         "lastEnrichmentError": error,
        #         "enrichmentAttempts": {"increment": 1}
        #     }
        # )

    async def _send_completion_prompt(
        self,
        user_id: str,
        missing_sources: list[str],
    ) -> None:
        """
        Prompt user to manually add missing profile links.

        Args:
            user_id: User identifier
            missing_sources: List of platforms not found
        """
        if not self.notification_service:
            logger.debug(
                f"Would send completion prompt to {user_id} for: {missing_sources}"
            )
            return

        # Format missing sources for display
        missing_display = self._format_source_names(missing_sources)

        await self.notification_service.send(
            user_id,
            {
                "type": "profile_incomplete",
                "title": "Complete your profile for better matches",
                "body": f"We couldn't find your {missing_display}. Add them manually for better recommendations.",
                "action": {
                    "type": "open_profile_edit",
                    "highlight_fields": self._get_field_names(missing_sources),
                },
            },
        )

    async def _send_manual_input_request(self, user_id: str) -> None:
        """
        Prompt TIER_3 users to manually add their profiles.

        Args:
            user_id: User identifier
        """
        if not self.notification_service:
            logger.debug(f"Would send manual input request to {user_id}")
            return

        await self.notification_service.send(
            user_id,
            {
                "type": "profile_manual_needed",
                "title": "Help us find better matches for you",
                "body": "Add your LinkedIn or GitHub to get personalized recommendations.",
                "action": {
                    "type": "open_profile_edit",
                    "fields": [
                        "linkedInUrl",
                        "githubUsername",
                        "bio",
                        "skillsToOffer",
                    ],
                },
            },
        )

    def _format_source_names(self, sources: list[str]) -> str:
        """Format source names for user-friendly display."""
        source_names = {
            "linkedin": "LinkedIn",
            "github": "GitHub",
            "twitter": "Twitter/X",
            "youtube": "YouTube",
            "instagram": "Instagram",
            "facebook": "Facebook",
        }

        formatted = [source_names.get(s, s) for s in sources]

        if len(formatted) == 1:
            return formatted[0]
        elif len(formatted) == 2:
            return f"{formatted[0]} and {formatted[1]}"
        else:
            return f"{', '.join(formatted[:-1])}, and {formatted[-1]}"

    def _get_field_names(self, sources: list[str]) -> list[str]:
        """Get database field names for sources."""
        field_map = {
            "linkedin": "linkedInUrl",
            "github": "githubUsername",
            "twitter": "twitterHandle",
            "youtube": "youtubeChannelUrl",
            "instagram": "instagramHandle",
            "facebook": "facebookProfileUrl",
        }
        return [field_map.get(s, s) for s in sources if s in field_map]


class ProfileTierManager:
    """
    Manages profile tier assignments and transitions.

    Ensures users aren't penalized for failed enrichment
    and can still appear in recommendations.
    """

    @staticmethod
    def get_tier_from_sources(sources_count: int) -> ProfileTier:
        """
        Determine tier based on number of sources found.

        Args:
            sources_count: Number of platforms found

        Returns:
            Appropriate profile tier
        """
        if sources_count >= 3:
            return ProfileTier.TIER_1_RICH
        elif sources_count >= 1:
            return ProfileTier.TIER_2_BASIC
        else:
            return ProfileTier.TIER_3_MANUAL

    @staticmethod
    def get_tier_description(tier: ProfileTier) -> dict[str, Any]:
        """
        Get human-readable description of a profile tier.

        Args:
            tier: Profile tier

        Returns:
            Dict with title, description, and completion info
        """
        descriptions = {
            ProfileTier.TIER_0_PENDING: {
                "title": "Pending Enrichment",
                "description": "Profile enrichment has not been attempted yet.",
                "completion_percent": 0,
                "recommendation_quality": "basic",
            },
            ProfileTier.TIER_1_RICH: {
                "title": "Rich Profile",
                "description": "Full profile with 3+ verified sources.",
                "completion_percent": 100,
                "recommendation_quality": "excellent",
            },
            ProfileTier.TIER_2_BASIC: {
                "title": "Basic Profile",
                "description": "Partial profile with 1-2 sources. Add more for better matches.",
                "completion_percent": 60,
                "recommendation_quality": "good",
            },
            ProfileTier.TIER_3_MANUAL: {
                "title": "Manual Profile",
                "description": "No external sources found. Add profiles manually.",
                "completion_percent": 30,
                "recommendation_quality": "limited",
            },
        }

        return descriptions.get(
            tier,
            {
                "title": "Unknown",
                "description": "Unknown tier status.",
                "completion_percent": 0,
                "recommendation_quality": "unknown",
            },
        )

    @staticmethod
    def should_retry_enrichment(
        current_tier: ProfileTier,
        attempts: int,
        max_attempts: int = 3,
    ) -> bool:
        """
        Determine if enrichment should be retried.

        Args:
            current_tier: Current profile tier
            attempts: Number of enrichment attempts
            max_attempts: Maximum allowed attempts

        Returns:
            True if retry is recommended
        """
        # Don't retry if already TIER_1
        if current_tier == ProfileTier.TIER_1_RICH:
            return False

        # Don't exceed max attempts
        if attempts >= max_attempts:
            return False

        # Retry for pending or failed enrichments
        return current_tier in (ProfileTier.TIER_0_PENDING, ProfileTier.TIER_3_MANUAL)
