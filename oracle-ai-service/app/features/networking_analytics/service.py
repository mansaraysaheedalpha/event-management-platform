# app/features/networking_analytics/service.py
"""
Networking analytics computation service.

Computes engagement metrics for organizer dashboards.
Results are cached for 1 hour to avoid expensive recomputation.

Integration:
- Fetches data from real-time-service via HTTP
- Publishes analytics events via Kafka for frontend updates
"""

import json
import logging
from datetime import datetime, timezone
from typing import Any, Optional

import redis.asyncio as aioredis

from app.core.config import settings
from app.features.networking_analytics.schemas import (
    GoalPairCount,
    InterestCount,
    NetworkingAnalyticsResponse,
    TierDistribution,
)
from app.integrations.kafka_publisher import get_kafka_publisher
from app.integrations.realtime_client import get_realtime_client

logger = logging.getLogger(__name__)


class NetworkingAnalyticsService:
    """
    Computes networking engagement metrics for organizer dashboard.

    Features:
    - Caches computed analytics for 1 hour
    - Computes metrics from event data
    - Provides industry benchmark comparisons
    """

    # Industry benchmarks for comparison
    BENCHMARKS = {
        "active_networking_rate": {"avg": 0.10, "target": 0.30},  # % attending who network
        "recommendation_view_rate": {"avg": 0.15, "target": 0.50},
        "follow_up_response_rate": {"avg": 0.10, "target": 0.30},
        "connections_per_attendee": {"avg": 1.5, "target": 3.0},
        "huddle_accept_rate": {"avg": 0.25, "target": 0.40},
    }

    def __init__(self, redis_client: Optional[aioredis.Redis] = None):
        """
        Initialize analytics service.

        Args:
            redis_client: Optional Redis client for caching
        """
        self.redis_client = redis_client

    async def fetch_event_data(self, event_id: str) -> dict[str, list[dict]]:
        """
        Fetch all event data from real-time-service.

        Args:
            event_id: Event identifier

        Returns:
            Dict containing all event data for analytics computation
        """
        client = await get_realtime_client()

        # Fetch all data in parallel for performance
        import asyncio

        attendees_task = client.get_event_attendees(event_id, include_profiles=True)
        recommendations_task = client.get_event_recommendations(event_id)
        connections_task = client.get_event_connections(event_id)
        pings_task = client.get_event_pings(event_id)
        dms_task = client.get_event_dms(event_id)
        huddles_task = client.get_event_huddles(event_id)
        huddle_invites_task = client.get_huddle_invites(event_id)
        follow_ups_task = client.get_event_follow_ups(event_id)

        results = await asyncio.gather(
            attendees_task,
            recommendations_task,
            connections_task,
            pings_task,
            dms_task,
            huddles_task,
            huddle_invites_task,
            follow_ups_task,
            return_exceptions=True,
        )

        # Handle any exceptions gracefully
        def safe_result(result, default=None):
            if default is None:
                default = []
            if isinstance(result, Exception):
                logger.warning(f"Failed to fetch data: {result}")
                return default
            return result

        return {
            "attendees": safe_result(results[0]),
            "recommendations": safe_result(results[1]),
            "connections": safe_result(results[2]),
            "pings": safe_result(results[3]),
            "dms": safe_result(results[4]),
            "huddles": safe_result(results[5]),
            "huddle_invites": safe_result(results[6]),
            "follow_ups": safe_result(results[7]),
        }

    def _cache_key(self, event_id: str) -> str:
        """Generate cache key for event analytics."""
        return f"networking_analytics:{event_id}"

    async def _get_cached(self, event_id: str) -> Optional[dict[str, Any]]:
        """Get cached analytics."""
        if not self.redis_client:
            return None

        try:
            cached = await self.redis_client.get(self._cache_key(event_id))
            if cached:
                logger.debug(f"Cache hit for analytics {event_id}")
                return json.loads(cached)
        except Exception as e:
            logger.warning(f"Cache read error: {e}")

        return None

    async def _set_cached(self, event_id: str, data: dict[str, Any]) -> None:
        """Cache analytics."""
        if not self.redis_client:
            return

        try:
            await self.redis_client.setex(
                self._cache_key(event_id),
                settings.ANALYTICS_CACHE_TTL_SECONDS,
                json.dumps(data, default=str),
            )
            logger.debug(f"Cached analytics for {event_id}")
        except Exception as e:
            logger.warning(f"Cache write error: {e}")

    async def compute_event_analytics(
        self,
        event_id: str,
        force_refresh: bool = False,
        fetch_from_service: bool = True,
        publish_event: bool = True,
        # Optional data overrides (for testing or batch processing)
        attendees: Optional[list[dict]] = None,
        recommendations: Optional[list[dict]] = None,
        connections: Optional[list[dict]] = None,
        pings: Optional[list[dict]] = None,
        dms: Optional[list[dict]] = None,
        huddles: Optional[list[dict]] = None,
        huddle_invites: Optional[list[dict]] = None,
        follow_ups: Optional[list[dict]] = None,
    ) -> NetworkingAnalyticsResponse:
        """
        Compute all networking metrics for an event.

        Args:
            event_id: Event identifier
            force_refresh: Force recomputation even if cached
            fetch_from_service: Fetch data from real-time-service (default True)
            publish_event: Publish Kafka event after computation (default True)
            attendees: Optional override for attendee data
            recommendations: Optional override for recommendation data
            connections: Optional override for connection data
            pings: Optional override for ping data
            dms: Optional override for DM data
            huddles: Optional override for huddle data
            huddle_invites: Optional override for huddle invite data
            follow_ups: Optional override for follow-up data

        Returns:
            Complete analytics response
        """
        # Check cache first (unless forced refresh)
        if not force_refresh:
            cached = await self._get_cached(event_id)
            if cached:
                return NetworkingAnalyticsResponse(**cached)

        # Fetch from real-time-service if no data provided
        if fetch_from_service and all(
            x is None for x in [
                attendees, recommendations, connections, pings,
                dms, huddles, huddle_invites, follow_ups
            ]
        ):
            logger.info(f"Fetching event data from real-time-service for {event_id}")
            try:
                event_data = await self.fetch_event_data(event_id)
                attendees = event_data["attendees"]
                recommendations = event_data["recommendations"]
                connections = event_data["connections"]
                pings = event_data["pings"]
                dms = event_data["dms"]
                huddles = event_data["huddles"]
                huddle_invites = event_data["huddle_invites"]
                follow_ups = event_data["follow_ups"]
            except Exception as e:
                logger.error(f"Failed to fetch event data: {e}")
                # Fall back to empty data
                pass

        # Use defaults for any missing data
        attendees = attendees or []
        recommendations = recommendations or []
        connections = connections or []
        pings = pings or []
        dms = dms or []
        huddles = huddles or []
        huddle_invites = huddle_invites or []
        follow_ups = follow_ups or []

        # Compute metrics
        total_attendees = len(attendees)

        # Enrichment metrics
        enriched = [a for a in attendees if a.get("enrichment_status") == "COMPLETED"]
        opted_in = [a for a in attendees if a.get("enrichment_status") != "OPTED_OUT"]
        enrichment_rate = len(enriched) / len(opted_in) if opted_in else 0.0

        # Tier distribution
        tier_dist = self._compute_tier_distribution(attendees)

        # Recommendation metrics
        viewed_recs = [r for r in recommendations if r.get("viewed")]
        rec_view_rate = len(viewed_recs) / len(recommendations) if recommendations else 0.0

        # Connection metrics
        connections_per_attendee = len(connections) / total_attendees if total_attendees else 0.0

        # Huddle metrics
        accepted_invites = [i for i in huddle_invites if i.get("status") == "ACCEPTED"]
        attended_invites = [i for i in huddle_invites if i.get("status") == "ATTENDED"]

        huddle_accept_rate = (
            len(accepted_invites) / len(huddle_invites) if huddle_invites else 0.0
        )
        huddle_attend_rate = (
            len(attended_invites) / len(accepted_invites) if accepted_invites else 0.0
        )

        avg_huddle_size = (
            sum(h.get("participant_count", 0) for h in huddles) / len(huddles)
            if huddles
            else 0.0
        )

        # Follow-up metrics
        responded_follow_ups = [f for f in follow_ups if f.get("response_status") == "RESPONDED"]
        follow_up_response_rate = (
            len(responded_follow_ups) / len(follow_ups) if follow_ups else 0.0
        )

        # Top matching factors
        top_interests = self._compute_top_interests(connections, attendees)
        top_goal_pairs = self._compute_top_goal_pairs(connections, attendees)

        # Build response
        analytics = NetworkingAnalyticsResponse(
            event_id=event_id,
            computed_at=datetime.now(timezone.utc),
            total_attendees=total_attendees,
            profiles_enriched=len(enriched),
            enrichment_rate=enrichment_rate,
            tier_distribution=tier_dist,
            recommendations_generated=len(recommendations),
            recommendations_viewed=len(viewed_recs),
            recommendation_view_rate=rec_view_rate,
            total_pings=len(pings),
            total_dms=len(dms),
            total_connections=len(connections),
            connections_per_attendee=connections_per_attendee,
            huddles_formed=len(huddles),
            huddle_invites_sent=len(huddle_invites),
            huddle_accept_rate=huddle_accept_rate,
            huddle_attend_rate=huddle_attend_rate,
            avg_huddle_size=avg_huddle_size,
            follow_ups_sent=len(follow_ups),
            follow_up_response_rate=follow_up_response_rate,
            top_interests=top_interests,
            top_goal_pairs=top_goal_pairs,
            benchmark_comparison=self._compute_benchmarks(
                connections_per_attendee=connections_per_attendee,
                recommendation_view_rate=rec_view_rate,
                follow_up_response_rate=follow_up_response_rate,
                huddle_accept_rate=huddle_accept_rate,
            ),
        )

        # Cache the result
        await self._set_cached(event_id, analytics.model_dump())

        logger.info(f"Computed analytics for event {event_id}")

        # Publish Kafka event for frontend dashboard refresh
        if publish_event:
            try:
                kafka = get_kafka_publisher()
                kafka.publish_analytics_computed(
                    event_id=event_id,
                    total_attendees=analytics.total_attendees,
                    total_connections=analytics.total_connections,
                    connections_per_attendee=analytics.connections_per_attendee,
                    enrichment_rate=analytics.enrichment_rate,
                    recommendation_view_rate=analytics.recommendation_view_rate,
                )
                logger.debug(f"Published analytics computed event for {event_id}")
            except Exception as e:
                # Don't fail analytics computation if Kafka is down
                logger.warning(f"Failed to publish analytics event: {e}")

        return analytics

    def _compute_tier_distribution(
        self,
        attendees: list[dict],
    ) -> TierDistribution:
        """Compute profile tier distribution."""
        tiers = {
            "TIER_0_PENDING": 0,
            "TIER_1_RICH": 0,
            "TIER_2_BASIC": 0,
            "TIER_3_MANUAL": 0,
        }

        for attendee in attendees:
            tier = attendee.get("profile_tier", "TIER_0_PENDING")
            if tier in tiers:
                tiers[tier] += 1

        return TierDistribution(
            tier_0_pending=tiers["TIER_0_PENDING"],
            tier_1_rich=tiers["TIER_1_RICH"],
            tier_2_basic=tiers["TIER_2_BASIC"],
            tier_3_manual=tiers["TIER_3_MANUAL"],
        )

    def _compute_top_interests(
        self,
        connections: list[dict],
        attendees: list[dict],
    ) -> list[InterestCount]:
        """Find which interests led to the most connections."""
        # Build user interest lookup
        user_interests: dict[str, set[str]] = {}
        for attendee in attendees:
            user_id = attendee.get("user_id")
            interests = set(attendee.get("interests", []))
            if user_id:
                user_interests[user_id] = interests

        # Count shared interests in connections
        interest_counts: dict[str, int] = {}

        for conn in connections:
            user1_id = conn.get("user_id")
            user2_id = conn.get("connected_user_id")

            user1_interests = user_interests.get(user1_id, set())
            user2_interests = user_interests.get(user2_id, set())

            shared = user1_interests & user2_interests

            for interest in shared:
                interest_counts[interest] = interest_counts.get(interest, 0) + 1

        # Sort by count and return top 10
        sorted_interests = sorted(
            interest_counts.items(),
            key=lambda x: x[1],
            reverse=True,
        )[:10]

        return [
            InterestCount(interest=interest, count=count)
            for interest, count in sorted_interests
        ]

    def _compute_top_goal_pairs(
        self,
        connections: list[dict],
        attendees: list[dict],
    ) -> list[GoalPairCount]:
        """Find which goal combinations led to connections."""
        # Build user goals lookup
        user_goals: dict[str, list[str]] = {}
        for attendee in attendees:
            user_id = attendee.get("user_id")
            goals = attendee.get("goals", [])
            if user_id:
                user_goals[user_id] = goals

        # Count goal pairs in connections
        pair_counts: dict[tuple[str, str], int] = {}

        for conn in connections:
            user1_id = conn.get("user_id")
            user2_id = conn.get("connected_user_id")

            user1_goals = user_goals.get(user1_id, [])
            user2_goals = user_goals.get(user2_id, [])

            for g1 in user1_goals:
                for g2 in user2_goals:
                    pair = tuple(sorted([g1, g2]))
                    pair_counts[pair] = pair_counts.get(pair, 0) + 1

        # Sort by count and return top 10
        sorted_pairs = sorted(
            pair_counts.items(),
            key=lambda x: x[1],
            reverse=True,
        )[:10]

        return [
            GoalPairCount(pair=list(pair), count=count)
            for pair, count in sorted_pairs
        ]

    def _compute_benchmarks(
        self,
        connections_per_attendee: float,
        recommendation_view_rate: float,
        follow_up_response_rate: float,
        huddle_accept_rate: float,
    ) -> dict[str, dict]:
        """Compute benchmark comparisons."""
        return {
            "connections_per_attendee": {
                "your_value": connections_per_attendee,
                "industry_avg": self.BENCHMARKS["connections_per_attendee"]["avg"],
                "target": self.BENCHMARKS["connections_per_attendee"]["target"],
                "is_above_target": connections_per_attendee >= self.BENCHMARKS["connections_per_attendee"]["target"],
            },
            "recommendation_view_rate": {
                "your_value": recommendation_view_rate,
                "industry_avg": self.BENCHMARKS["recommendation_view_rate"]["avg"],
                "target": self.BENCHMARKS["recommendation_view_rate"]["target"],
                "is_above_target": recommendation_view_rate >= self.BENCHMARKS["recommendation_view_rate"]["target"],
            },
            "follow_up_response_rate": {
                "your_value": follow_up_response_rate,
                "industry_avg": self.BENCHMARKS["follow_up_response_rate"]["avg"],
                "target": self.BENCHMARKS["follow_up_response_rate"]["target"],
                "is_above_target": follow_up_response_rate >= self.BENCHMARKS["follow_up_response_rate"]["target"],
            },
            "huddle_accept_rate": {
                "your_value": huddle_accept_rate,
                "industry_avg": self.BENCHMARKS["huddle_accept_rate"]["avg"],
                "target": self.BENCHMARKS["huddle_accept_rate"]["target"],
                "is_above_target": huddle_accept_rate >= self.BENCHMARKS["huddle_accept_rate"]["target"],
            },
        }

    def export_analytics_json(
        self,
        analytics: NetworkingAnalyticsResponse,
    ) -> dict[str, Any]:
        """
        Export analytics to JSON format.

        Args:
            analytics: Computed analytics

        Returns:
            JSON-serializable dict
        """
        return {
            "event_id": analytics.event_id,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "summary": {
                "total_attendees": analytics.total_attendees,
                "total_connections": analytics.total_connections,
                "connections_per_attendee": analytics.connections_per_attendee,
                "enrichment_rate": analytics.enrichment_rate,
            },
            "enrichment": {
                "profiles_enriched": analytics.profiles_enriched,
                "enrichment_rate": analytics.enrichment_rate,
                "tier_distribution": analytics.tier_distribution.model_dump(),
            },
            "recommendations": {
                "generated": analytics.recommendations_generated,
                "viewed": analytics.recommendations_viewed,
                "view_rate": analytics.recommendation_view_rate,
            },
            "connections": {
                "total_pings": analytics.total_pings,
                "total_dms": analytics.total_dms,
                "total_connections": analytics.total_connections,
                "per_attendee": analytics.connections_per_attendee,
            },
            "huddles": {
                "formed": analytics.huddles_formed,
                "invites_sent": analytics.huddle_invites_sent,
                "accept_rate": analytics.huddle_accept_rate,
                "attend_rate": analytics.huddle_attend_rate,
                "avg_size": analytics.avg_huddle_size,
            },
            "follow_ups": {
                "sent": analytics.follow_ups_sent,
                "response_rate": analytics.follow_up_response_rate,
            },
            "top_factors": {
                "interests": [i.model_dump() for i in analytics.top_interests],
                "goal_pairs": [g.model_dump() for g in analytics.top_goal_pairs],
            },
            "benchmarks": analytics.benchmark_comparison,
        }


# Singleton service instance
_service: Optional[NetworkingAnalyticsService] = None


async def get_analytics_service() -> NetworkingAnalyticsService:
    """Get or create analytics service singleton."""
    global _service
    if _service is None:
        try:
            redis_client = await aioredis.from_url(
                settings.REDIS_URL,
                encoding="utf-8",
                decode_responses=True,
            )
        except Exception as e:
            logger.warning(f"Could not connect to Redis: {e}")
            redis_client = None

        _service = NetworkingAnalyticsService(redis_client=redis_client)

    return _service
