# app/features/enrichment/router.py
"""
API endpoints for profile enrichment.

Provides:
- POST /enrichment/{user_id} - Trigger background enrichment
- GET /enrichment/status/{user_id} - Check enrichment status
- POST /enrichment/batch - Batch enrich event attendees
- POST /enrichment/sync/{user_id} - Sync enrichment (debug only)
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.core.config import settings
from app.core.exceptions import (
    EnrichmentAlreadyProcessingError,
    EnrichmentDisabledError,
    EnrichmentOptedOutError,
    UserRateLimitError,
)
from app.features.enrichment.schemas import (
    BatchEnrichmentRequest,
    BatchEnrichmentResponse,
    EnrichmentRequest,
    EnrichmentResponse,
    EnrichmentStatusResponse,
)
from app.features.enrichment.service import get_enrichment_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/enrichment", tags=["Profile Enrichment"])


@router.post(
    "/{user_id}",
    response_model=EnrichmentResponse,
    summary="Trigger profile enrichment",
    description="Queue a user's profile for background enrichment using AI-powered research.",
)
async def enrich_user_profile(
    user_id: str,
    request: EnrichmentRequest,
    current_status: Optional[str] = Query(
        None,
        description="Current enrichment status (PENDING, PROCESSING, COMPLETED, OPTED_OUT)",
    ),
) -> EnrichmentResponse:
    """
    Trigger profile enrichment for a user.

    The enrichment runs in the background and searches for:
    - LinkedIn profiles
    - GitHub accounts
    - Twitter/X profiles
    - YouTube channels
    - Instagram profiles
    - Facebook pages

    Returns immediately with a task ID for tracking.
    """
    service = get_enrichment_service()

    try:
        result = await service.enrich_user_async(
            user_id=user_id,
            name=request.name,
            email=request.email,
            company=request.company,
            role=request.role,
            linkedin_url=request.linkedin_url,
            github_username=request.github_username,
            twitter_handle=request.twitter_handle,
            current_status=current_status,
        )

        return EnrichmentResponse(
            status=result["status"],
            message=result["message"],
            task_id=result.get("task_id"),
        )

    except EnrichmentDisabledError:
        raise HTTPException(
            status_code=503,
            detail="Profile enrichment is currently disabled. Please configure API keys.",
        )
    except EnrichmentOptedOutError:
        return EnrichmentResponse(
            status="opted_out",
            message="User has opted out of profile enrichment",
        )
    except EnrichmentAlreadyProcessingError:
        return EnrichmentResponse(
            status="processing",
            message="Enrichment already in progress for this user",
        )
    except UserRateLimitError as e:
        raise HTTPException(
            status_code=429,
            detail=f"Rate limit exceeded. Try again in {e.period_seconds // 60} minutes.",
        )
    except Exception as e:
        logger.error(f"Enrichment error for user {user_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail="An error occurred while starting enrichment",
        )


@router.get(
    "/status/{user_id}",
    response_model=EnrichmentStatusResponse,
    summary="Get enrichment status",
    description="Check the current enrichment status for a user.",
)
async def get_enrichment_status(
    user_id: str,
    # These would typically come from a database lookup
    # For now, accepting as query params for demo
    status: Optional[str] = Query(None, description="Current status from database"),
    tier: Optional[str] = Query(None, description="Current tier from database"),
) -> EnrichmentStatusResponse:
    """
    Get the current enrichment status for a user.

    Returns:
    - status: PENDING, PROCESSING, COMPLETED, FAILED, or OPTED_OUT
    - profile_tier: TIER_0_PENDING, TIER_1_RICH, TIER_2_BASIC, or TIER_3_MANUAL
    - enriched_at: Timestamp when enrichment completed
    - sources: List of platforms found (linkedin, github, etc.)
    """
    service = get_enrichment_service()

    result = service.get_enrichment_status(
        user_id=user_id,
        status=status,
        tier=tier,
    )

    return EnrichmentStatusResponse(
        user_id=result["user_id"],
        status=result["status"],
        profile_tier=result.get("profile_tier"),
        enriched_at=result.get("enriched_at"),
        sources=result.get("sources", []),
    )


@router.post(
    "/batch",
    response_model=BatchEnrichmentResponse,
    summary="Batch enrich event attendees",
    description="Queue all attendees for an event for background enrichment.",
)
async def batch_enrich_event(
    request: BatchEnrichmentRequest,
) -> BatchEnrichmentResponse:
    """
    Queue all attendees for an event for enrichment.

    Enrichments are spread over time to avoid API rate limits.
    Typically processes ~100 profiles per hour.
    """
    service = get_enrichment_service()

    try:
        result = await service.enrich_event_attendees(
            event_id=request.event_id,
            attendees=request.attendees,
        )

        return BatchEnrichmentResponse(
            event_id=result["event_id"],
            queued=len([a for a in request.attendees if a.get("enrichment_status") not in ("COMPLETED", "OPTED_OUT")]),
            skipped=len([a for a in request.attendees if a.get("enrichment_status") in ("COMPLETED", "OPTED_OUT")]),
            total=len(request.attendees),
            message=result["message"],
        )

    except EnrichmentDisabledError:
        raise HTTPException(
            status_code=503,
            detail="Profile enrichment is currently disabled",
        )
    except Exception as e:
        logger.error(f"Batch enrichment error for event {request.event_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail="An error occurred while queuing batch enrichment",
        )


@router.post(
    "/sync/{user_id}",
    response_model=EnrichmentResponse,
    summary="Synchronous enrichment (debug only)",
    description="Run enrichment synchronously. WARNING: Blocks request for 5-30 seconds.",
    include_in_schema=settings.ANTHROPIC_API_KEY != "",  # Only show if configured
)
async def enrich_user_sync(
    user_id: str,
    request: EnrichmentRequest,
) -> EnrichmentResponse:
    """
    Run enrichment synchronously (FOR DEBUGGING ONLY).

    WARNING: This blocks the HTTP request for 5-30 seconds.
    Do not use in production - use the async endpoint instead.
    """
    service = get_enrichment_service()

    try:
        result = await service.enrich_user_sync(
            user_id=user_id,
            name=request.name,
            email=request.email,
            company=request.company,
            role=request.role,
            linkedin_url=request.linkedin_url,
            github_username=request.github_username,
            twitter_handle=request.twitter_handle,
        )

        return EnrichmentResponse(
            status=result.status.value,
            message=f"Enrichment completed with {len(result.sources_found)} sources",
            profile_tier=result.profile_tier.value,
            sources_found=result.sources_found,
        )

    except EnrichmentDisabledError:
        raise HTTPException(
            status_code=503,
            detail="Profile enrichment is currently disabled",
        )
    except UserRateLimitError as e:
        raise HTTPException(
            status_code=429,
            detail=f"Rate limit exceeded. Try again later.",
        )
    except Exception as e:
        logger.error(f"Sync enrichment error for user {user_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail=str(e),
        )


@router.get(
    "/health",
    summary="Enrichment service health",
    description="Check if the enrichment service is configured and healthy.",
)
async def enrichment_health() -> dict:
    """
    Check enrichment service health.

    Returns configuration status and circuit breaker states.
    """
    from app.core.circuit_breaker import get_all_breaker_stats

    breaker_stats = await get_all_breaker_stats()

    return {
        "enabled": settings.enrichment_enabled,
        "tavily_configured": bool(settings.TAVILY_API_KEY),
        "anthropic_configured": bool(settings.ANTHROPIC_API_KEY),
        "github_token_configured": bool(settings.GITHUB_PUBLIC_API_TOKEN),
        "circuit_breakers": breaker_stats,
    }
