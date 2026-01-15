# app/features/networking_analytics/router.py
"""
API endpoints for networking analytics.

Provides organizers with metrics on networking engagement at their events.
"""

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Query

from app.features.networking_analytics.schemas import (
    AnalyticsComputeRequest,
    AnalyticsExportResponse,
    AnalyticsSummaryResponse,
    NetworkingAnalyticsResponse,
)
from app.features.networking_analytics.service import get_analytics_service

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/networking-analytics",
    tags=["Networking Analytics"],
)


@router.get(
    "/{event_id}",
    response_model=NetworkingAnalyticsResponse,
    summary="Get networking analytics",
    description="Get complete networking engagement analytics for an event.",
)
async def get_event_analytics(
    event_id: str,
    force_refresh: bool = Query(
        False,
        description="Force recomputation even if cached",
    ),
) -> NetworkingAnalyticsResponse:
    """
    Get networking analytics for an event.

    Returns comprehensive metrics including:
    - Enrichment rates and tier distribution
    - Recommendation engagement
    - Connection and ping metrics
    - Huddle performance
    - Follow-up response rates
    - Top matching factors (interests and goals)
    - Industry benchmark comparisons

    Results are cached for 1 hour unless force_refresh is true.
    """
    service = await get_analytics_service()

    try:
        # Automatically fetches data from real-time-service and publishes
        # Kafka event for frontend dashboard updates
        analytics = await service.compute_event_analytics(
            event_id=event_id,
            force_refresh=force_refresh,
        )

        return analytics

    except Exception as e:
        logger.error(f"Analytics computation error for event {event_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to compute analytics",
        )


@router.get(
    "/{event_id}/summary",
    response_model=AnalyticsSummaryResponse,
    summary="Get analytics summary",
    description="Get a quick summary of networking analytics for dashboard cards.",
)
async def get_analytics_summary(
    event_id: str,
) -> AnalyticsSummaryResponse:
    """
    Get a quick summary of networking analytics.

    Lighter-weight endpoint for dashboard overview cards.
    """
    service = await get_analytics_service()

    try:
        analytics = await service.compute_event_analytics(event_id=event_id)

        return AnalyticsSummaryResponse(
            event_id=event_id,
            total_attendees=analytics.total_attendees,
            total_connections=analytics.total_connections,
            connections_per_attendee=analytics.connections_per_attendee,
            enrichment_rate=analytics.enrichment_rate,
            recommendation_view_rate=analytics.recommendation_view_rate,
            computed_at=analytics.computed_at,
        )

    except Exception as e:
        logger.error(f"Analytics summary error for event {event_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to get analytics summary",
        )


@router.post(
    "/{event_id}/compute",
    response_model=NetworkingAnalyticsResponse,
    summary="Force compute analytics",
    description="Force recomputation of analytics, bypassing cache.",
)
async def compute_analytics(
    event_id: str,
    request: AnalyticsComputeRequest,
) -> NetworkingAnalyticsResponse:
    """
    Force computation/refresh of analytics.

    Use this to get fresh metrics after significant event activity.
    """
    service = await get_analytics_service()

    try:
        analytics = await service.compute_event_analytics(
            event_id=event_id,
            force_refresh=True,
        )

        return analytics

    except Exception as e:
        logger.error(f"Analytics recomputation error for event {event_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to recompute analytics",
        )


@router.get(
    "/{event_id}/export",
    response_model=AnalyticsExportResponse,
    summary="Export analytics",
    description="Export analytics data for reporting.",
)
async def export_analytics(
    event_id: str,
    format: str = Query(
        "json",
        description="Export format (json)",
        regex="^(json)$",  # Only JSON supported for now
    ),
) -> AnalyticsExportResponse:
    """
    Export analytics data for external reporting.

    Currently supports JSON format. Data includes all metrics
    and is structured for easy import into BI tools.
    """
    service = await get_analytics_service()

    try:
        analytics = await service.compute_event_analytics(event_id=event_id)
        export_data = service.export_analytics_json(analytics)

        return AnalyticsExportResponse(
            event_id=event_id,
            format=format,
            data=export_data,
            generated_at=datetime.now(timezone.utc),
        )

    except Exception as e:
        logger.error(f"Analytics export error for event {event_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to export analytics",
        )


@router.get(
    "/{event_id}/benchmarks",
    summary="Get benchmark comparison",
    description="Get detailed benchmark comparison against industry averages.",
)
async def get_benchmarks(
    event_id: str,
) -> dict:
    """
    Get detailed benchmark comparison for the event.

    Compares your event's networking metrics against:
    - Industry averages
    - Target goals

    Helps organizers understand how their event performs.
    """
    service = await get_analytics_service()

    try:
        analytics = await service.compute_event_analytics(event_id=event_id)

        return {
            "event_id": event_id,
            "benchmarks": analytics.benchmark_comparison,
            "computed_at": analytics.computed_at.isoformat(),
        }

    except Exception as e:
        logger.error(f"Benchmark fetch error for event {event_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to get benchmarks",
        )


@router.get(
    "/{event_id}/top-factors",
    summary="Get top matching factors",
    description="Get the interests and goals driving the most connections.",
)
async def get_top_factors(
    event_id: str,
    limit: int = Query(10, ge=1, le=50, description="Number of top factors to return"),
) -> dict:
    """
    Get the top matching factors for the event.

    Shows which interests and goal combinations are
    creating the most connections at the event.
    """
    service = await get_analytics_service()

    try:
        analytics = await service.compute_event_analytics(event_id=event_id)

        return {
            "event_id": event_id,
            "top_interests": [
                {"interest": i.interest, "connections": i.count}
                for i in analytics.top_interests[:limit]
            ],
            "top_goal_pairs": [
                {"goals": g.pair, "connections": g.count}
                for g in analytics.top_goal_pairs[:limit]
            ],
            "computed_at": analytics.computed_at.isoformat(),
        }

    except Exception as e:
        logger.error(f"Top factors fetch error for event {event_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to get top factors",
        )
