# app/api/v1/endpoints/venue_availability.py
"""Venue availability management endpoints (venue owner + public)."""
import logging
import json
from typing import Optional
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api import deps
from app.db.session import get_db
from app.crud import crud_venue_availability, crud_venue_waitlist
from app.schemas.venue_waitlist import (
    VenueAvailabilitySetRequest,
    VenueAvailabilityResponse,
    AvailabilityBadgeResponse,
    CircuitBreakerResolveResponse,
)
from app.schemas.token import TokenPayload
from app.models.venue import Venue
from app.utils.waitlist_cascade import trigger_cascade
from app.utils.kafka_helpers import get_kafka_singleton
from app.core.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/venues", tags=["Venue Availability"])

# Redis cache for public badge endpoint (if available)
try:
    import redis

    redis_client = redis.from_url(settings.REDIS_URL) if hasattr(settings, "REDIS_URL") else None
except Exception as e:
    logger.warning(f"Redis not available for caching: {e}")
    redis_client = None


# ── Helpers ───────────────────────────────────────────────────────────


def _check_venue_owner(db: Session, current_user: TokenPayload, venue_id: str):
    """Verify that the current user owns the venue."""
    venue = db.query(Venue).filter(Venue.id == venue_id).first()
    if not venue:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Venue not found"
        )
    if venue.organization_id != current_user.org_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized"
        )
    return venue


def _get_badge_data(db: Session, venue_id: str) -> dict:
    """Get badge data for a venue (color + label mapping)."""
    venue = db.query(Venue).filter(Venue.id == venue_id).first()
    if not venue:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Venue not found"
        )

    status_value = venue.availability_status or "not_set"

    # Color mapping
    colors = {
        "accepting_events": "green",
        "limited_availability": "yellow",
        "fully_booked": "red",
        "seasonal": "blue",
        "not_set": "gray",
    }

    # Label mapping
    labels = {
        "accepting_events": "Accepting Events",
        "limited_availability": "Limited Availability",
        "fully_booked": "Fully Booked",
        "seasonal": "Seasonal Venue",
        "not_set": "Status Unknown",
    }

    return {
        "venue_id": venue_id,
        "availability_status": status_value,
        "badge_color": colors.get(status_value, "gray"),
        "badge_label": labels.get(status_value, "Status Unknown"),
    }


# ── Venue Owner Endpoints (Auth Required) ────────────────────────────


@router.get("/{venueId}/availability")
def get_availability(
    venueId: str,
    db: Session = Depends(get_db),
    current_user: TokenPayload = Depends(deps.get_current_user),
):
    """
    Get venue's current availability status and inference data.
    Auth: Venue owner only.
    """
    _check_venue_owner(db, current_user, venueId)

    result = crud_venue_availability.get_venue_availability(db, venue_id=venueId)

    return result


@router.put("/{venueId}/availability")
def set_availability(
    venueId: str,
    request: VenueAvailabilitySetRequest,
    db: Session = Depends(get_db),
    current_user: TokenPayload = Depends(deps.get_current_user),
):
    """
    Manually set venue availability status.
    Creates a manual override that takes precedence over inference.
    If status='accepting_events' and venue has waitlist entries, triggers cascade.
    Auth: Venue owner only.
    """
    _check_venue_owner(db, current_user, venueId)

    venue = crud_venue_availability.set_venue_availability(
        db,
        venue_id=venueId,
        org_id=current_user.org_id,
        status=request.availability_status.value,
    )

    # Record signal
    signal_type = (
        "manual_available"
        if request.availability_status.value == "accepting_events"
        else "manual_unavailable"
    )
    try:
        crud_venue_availability.record_signal(
            db,
            venue_id=venueId,
            signal_type=signal_type,
            metadata={"set_by": current_user.sub},
        )
    except Exception as e:
        logger.error(f"Failed to record signal: {e}")

    # Emit Kafka event
    try:
        producer = get_kafka_singleton()
        if producer:
            event_data = {
                "event_type": "venue.availability_manual_set",
                "venue_id": venueId,
                "new_status": request.availability_status.value,
                "set_by": current_user.org_id,
                "timestamp": str(datetime.now(timezone.utc)),
            }
            producer.send("waitlist-events", value=event_data)
    except Exception as e:
        logger.error(f"Failed to emit Kafka event: {e}")

    # If accepting_events, trigger cascade
    if request.availability_status.value == "accepting_events":
        logger.info(f"Venue {venueId} set to accepting_events, checking for waitlist")
        trigger_cascade(db, venueId)

    # Invalidate cache
    if redis_client:
        try:
            cache_key = f"venue_avail_badge:{venueId}"
            redis_client.delete(cache_key)
        except Exception as e:
            logger.error(f"Failed to invalidate cache: {e}")

    return {
        "venue_id": venueId,
        "availability_status": venue.availability_status,
        "is_manual_override": True,
        "manual_override_at": venue.availability_manual_override_at,
    }


@router.delete("/{venueId}/availability/override")
def clear_override(
    venueId: str,
    db: Session = Depends(get_db),
    current_user: TokenPayload = Depends(deps.get_current_user),
):
    """
    Clear the manual override, returning to inference-driven status.
    Auth: Venue owner only.
    """
    _check_venue_owner(db, current_user, venueId)

    venue = crud_venue_availability.clear_manual_override(
        db, venue_id=venueId, org_id=current_user.org_id
    )

    # Invalidate cache
    if redis_client:
        try:
            cache_key = f"venue_avail_badge:{venueId}"
            redis_client.delete(cache_key)
        except Exception as e:
            logger.error(f"Failed to invalidate cache: {e}")

    return {
        "venue_id": venueId,
        "availability_status": venue.availability_status,
        "is_manual_override": False,
        "reverted_to_inferred": True,
    }


@router.post("/{venueId}/waitlist-circuit-breaker/resolve")
def resolve_circuit_breaker(
    venueId: str,
    db: Session = Depends(get_db),
    current_user: TokenPayload = Depends(deps.get_current_user),
):
    """
    Venue owner confirms the waitlist should remain active after circuit breaker pause.
    Resets the consecutive no-response counter and resumes the cascade.
    Auth: Venue owner only.
    """
    _check_venue_owner(db, current_user, venueId)

    # Validate and resolve
    result = crud_venue_waitlist.resolve_circuit_breaker(db, venue_id=venueId)

    # Emit Kafka event
    try:
        producer = get_kafka_singleton()
        if producer:
            event_data = {
                "event_type": "waitlist.circuit_breaker_resolved",
                "venue_id": venueId,
                "resolved_by": current_user.org_id,
                "timestamp": str(datetime.now(timezone.utc)),
            }
            producer.send("waitlist-events", value=event_data)
    except Exception as e:
        logger.error(f"Failed to emit Kafka event: {e}")

    # Trigger cascade to resume
    logger.info(f"Circuit breaker resolved for venue {venueId}, resuming cascade")
    trigger_cascade(db, venueId)

    # Check if next entry was offered
    next_entry = crud_venue_waitlist.get_next_waiting_entry(db, venue_id=venueId)
    next_entry_offered = None
    if next_entry and next_entry.status == "offered":
        next_entry_offered = next_entry.id

    return {
        "venue_id": venueId,
        "circuit_breaker_resolved": True,
        "cascade_resumed": True,
        "next_entry_offered": next_entry_offered,
    }


# ── Public Endpoint (No Auth) ─────────────────────────────────────────


@router.get("/{venueId}/availability/status")
def get_availability_badge(
    venueId: str,
    db: Session = Depends(get_db),
):
    """
    Get the public-facing availability status badge.
    Used by frontend for directory listings.
    Cached aggressively (Redis, 5-minute TTL).
    No auth required.
    """
    cache_key = f"venue_avail_badge:{venueId}"

    # Try cache first
    if redis_client:
        try:
            cached = redis_client.get(cache_key)
            if cached:
                logger.debug(f"Cache hit for {cache_key}")
                return json.loads(cached)
        except Exception as e:
            logger.error(f"Redis get failed: {e}")

    # Fetch from DB
    badge_data = _get_badge_data(db, venueId)

    # Cache it
    if redis_client:
        try:
            redis_client.setex(cache_key, 300, json.dumps(badge_data))  # 5 min TTL
        except Exception as e:
            logger.error(f"Redis set failed: {e}")

    return badge_data
