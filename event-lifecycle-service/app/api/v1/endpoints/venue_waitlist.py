# app/api/v1/endpoints/venue_waitlist.py
"""Organizer waitlist management endpoints."""
import logging
from typing import Optional
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session

from app.api import deps
from app.db.session import get_db
from app.crud import crud_venue_waitlist
from app.schemas.venue_waitlist import (
    WaitlistJoinRequest,
    WaitlistCancelRequest,
    WaitlistEntryResponse,
    WaitlistEntryListResponse,
    WaitlistConversionResponse,
    RFPBasicInfo,
)
from app.schemas.token import TokenPayload
from app.utils.waitlist_cascade import trigger_cascade
from app.utils.kafka_helpers import get_kafka_singleton
from app.models.venue_photo import VenuePhoto

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/organizations/{orgId}/waitlists", tags=["Venue Waitlist"])


# ── Helpers ───────────────────────────────────────────────────────────


def _check_org_auth(current_user: TokenPayload, orgId: str):
    if current_user.org_id != orgId:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized"
        )


def _build_entry_response(db: Session, entry) -> dict:
    """Build the full waitlist entry response dict."""
    # Get venue cover photo
    cover_photo_url = None
    if entry.venue:
        cover = (
            db.query(VenuePhoto.url)
            .filter(
                VenuePhoto.venue_id == entry.venue.id, VenuePhoto.is_cover == True
            )
            .first()
        )
        if cover:
            cover_photo_url = cover.url

    # Calculate queue position
    queue_position = crud_venue_waitlist.get_queue_position(db, entry=entry)

    # Calculate hold_remaining_seconds if offered
    hold_remaining_seconds = None
    if entry.status == "offered" and entry.hold_expires_at:
        now = datetime.now(timezone.utc)
        if entry.hold_expires_at > now:
            delta = entry.hold_expires_at - now
            hold_remaining_seconds = int(delta.total_seconds())

    return {
        "id": entry.id,
        "organization_id": entry.organization_id,
        "venue_id": entry.venue_id,
        "venue_name": entry.venue.name if entry.venue else "Unknown",
        "venue_slug": entry.venue.slug if entry.venue else None,
        "venue_city": entry.venue.city if entry.venue else None,
        "venue_country": entry.venue.country if entry.venue else None,
        "venue_cover_photo_url": cover_photo_url,
        "venue_availability_status": (
            entry.venue.availability_status if entry.venue else "not_set"
        ),
        "source_rfp_id": entry.source_rfp_id,
        "source_rfp_title": entry.source_rfp.title if entry.source_rfp else "Unknown",
        "source_rfp_venue_id": entry.source_rfp_venue_id,
        "desired_dates_start": entry.desired_dates_start,
        "desired_dates_end": entry.desired_dates_end,
        "dates_flexible": entry.dates_flexible,
        "attendance_min": entry.attendance_min,
        "attendance_max": entry.attendance_max,
        "event_type": entry.event_type,
        "space_requirements": entry.space_requirements or [],
        "status": entry.status,
        "queue_position": queue_position,
        "hold_offered_at": entry.hold_offered_at,
        "hold_expires_at": entry.hold_expires_at,
        "hold_remaining_seconds": hold_remaining_seconds,
        "hold_reminder_sent": entry.hold_reminder_sent,
        "converted_rfp_id": entry.converted_rfp_id,
        "cancellation_reason": entry.cancellation_reason,
        "cancellation_notes": entry.cancellation_notes,
        "expires_at": entry.expires_at,
        "still_interested_sent_at": entry.still_interested_sent_at,
        "still_interested_responded": entry.still_interested_responded,
        "created_at": entry.created_at,
        "updated_at": entry.updated_at,
    }


def _emit_kafka_event(event_type: str, entry, metadata: dict = None):
    """Helper to emit Kafka events for waitlist state transitions."""
    try:
        producer = get_kafka_singleton()
        if not producer:
            logger.warning("Kafka producer unavailable, skipping event")
            return

        event_data = {
            "event_type": event_type,
            "waitlist_entry_id": entry.id,
            "venue_id": entry.venue_id,
            "organization_id": entry.organization_id,
            "source_rfp_id": entry.source_rfp_id,
            "status": entry.status,
            "metadata": metadata or {},
            "timestamp": str(datetime.now(timezone.utc)),
        }
        producer.send("waitlist-events", value=event_data)
        logger.info(f"Emitted Kafka event: {event_type} for entry {entry.id}")
    except Exception as e:
        logger.error(f"Failed to emit Kafka event: {e}")


# ── Endpoints (API Contract Section 2.1) ─────────────────────────────


@router.post("", status_code=status.HTTP_201_CREATED)
def join_waitlist(
    orgId: str,
    request: WaitlistJoinRequest,
    db: Session = Depends(get_db),
    current_user: TokenPayload = Depends(deps.get_current_user),
):
    """
    Join a venue waitlist.
    Rate limit: Max 5 active entries per organizer.
    """
    _check_org_auth(current_user, orgId)

    entry = crud_venue_waitlist.create_waitlist_entry(
        db, org_id=orgId, rfp_venue_id=request.source_rfp_venue_id
    )

    # Emit Kafka event
    _emit_kafka_event("waitlist.joined", entry)

    return _build_entry_response(db, entry)


@router.get("", response_model=WaitlistEntryListResponse)
def list_waitlist_entries(
    orgId: str,
    status: Optional[str] = Query(None),
    active: Optional[bool] = Query(None, alias="active"),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db),
    current_user: TokenPayload = Depends(deps.get_current_user),
):
    """List organizer's waitlist entries."""
    _check_org_auth(current_user, orgId)

    result = crud_venue_waitlist.list_waitlist_entries(
        db,
        org_id=orgId,
        status=status,
        active_only=active or False,
        page=page,
        page_size=page_size,
    )

    # Build response entries
    entries = [_build_entry_response(db, e) for e in result["entries"]]

    return {
        "waitlist_entries": entries,
        "pagination": result["pagination"],
    }


@router.get("/{waitlistId}")
def get_waitlist_entry(
    orgId: str,
    waitlistId: str,
    db: Session = Depends(get_db),
    current_user: TokenPayload = Depends(deps.get_current_user),
):
    """Get waitlist entry detail."""
    _check_org_auth(current_user, orgId)

    entry = crud_venue_waitlist.get_waitlist_entry(
        db, entry_id=waitlistId, org_id=orgId
    )

    if not entry:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Waitlist entry not found"
        )

    return _build_entry_response(db, entry)


@router.post("/{waitlistId}/convert", status_code=status.HTTP_201_CREATED)
def convert_hold(
    orgId: str,
    waitlistId: str,
    db: Session = Depends(get_db),
    current_user: TokenPayload = Depends(deps.get_current_user),
):
    """
    Convert the hold into a new pre-filled RFP.
    Only allowed when status='offered' and hold has not expired.
    """
    _check_org_auth(current_user, orgId)

    entry = crud_venue_waitlist.get_waitlist_entry(
        db, entry_id=waitlistId, org_id=orgId
    )

    if not entry:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Waitlist entry not found"
        )

    result = crud_venue_waitlist.convert_hold(db, entry=entry, org_id=orgId)

    # Emit Kafka event
    _emit_kafka_event(
        "waitlist.converted",
        result["waitlist_entry"],
        {"new_rfp_id": result["new_rfp"].id},
    )

    # Build response
    waitlist_entry_data = _build_entry_response(db, result["waitlist_entry"])

    new_rfp = result["new_rfp"]
    venue_count = (
        db.query(db.execute("SELECT COUNT(*) FROM rfp_venues WHERE rfp_id = :rfp_id", {"rfp_id": new_rfp.id})).scalar()
        or 1
    )

    rfp_data = {
        "id": new_rfp.id,
        "title": new_rfp.title,
        "status": new_rfp.status,
        "venue_count": venue_count,
        "message": "New RFP created from waitlist hold. Review and send when ready.",
    }

    return {
        "waitlist_entry": waitlist_entry_data,
        "new_rfp": rfp_data,
    }


@router.post("/{waitlistId}/cancel")
def cancel_entry(
    orgId: str,
    waitlistId: str,
    request: WaitlistCancelRequest,
    db: Session = Depends(get_db),
    current_user: TokenPayload = Depends(deps.get_current_user),
):
    """
    Cancel a waitlist entry.
    If was in 'offered' state, triggers cascade to next person.
    """
    _check_org_auth(current_user, orgId)

    entry = crud_venue_waitlist.get_waitlist_entry(
        db, entry_id=waitlistId, org_id=orgId
    )

    if not entry:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Waitlist entry not found"
        )

    was_offered = entry.status == "offered"
    venue_id = entry.venue_id

    entry = crud_venue_waitlist.cancel_entry(
        db, entry=entry, reason=request.reason.value, notes=request.notes
    )

    # Emit Kafka event
    _emit_kafka_event(
        "waitlist.cancelled", entry, {"cancellation_reason": request.reason.value}
    )

    # If was offered, trigger cascade
    if was_offered:
        logger.info(f"Triggering cascade for venue {venue_id} after cancellation")
        trigger_cascade(db, venue_id)

    return _build_entry_response(db, entry)
