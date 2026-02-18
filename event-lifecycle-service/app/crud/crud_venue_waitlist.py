# app/crud/crud_venue_waitlist.py
import math
import logging
from typing import Optional
from datetime import datetime, timezone, timedelta
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func
from fastapi import HTTPException

from app.models.venue_waitlist_entry import VenueWaitlistEntry
from app.models.rfp_venue import RFPVenue
from app.models.rfp import RFP
from app.models.venue import Venue

logger = logging.getLogger(__name__)

# Active (non-terminal) statuses
ACTIVE_STATUSES = {"waiting", "offered"}
TERMINAL_STATUSES = {"converted", "expired", "cancelled"}

# Rate limits
MAX_ACTIVE_WAITLIST_ENTRIES = 5
MAX_ACTIVE_RFPS = 5


def count_active_entries(db: Session, org_id: str) -> int:
    """Count active waitlist entries for an organizer (for rate limiting)."""
    return (
        db.query(func.count(VenueWaitlistEntry.id))
        .filter(
            VenueWaitlistEntry.organization_id == org_id,
            VenueWaitlistEntry.status.in_(ACTIVE_STATUSES),
        )
        .scalar()
    )


def create_waitlist_entry(
    db: Session, *, org_id: str, rfp_venue_id: str
) -> VenueWaitlistEntry:
    """
    Create a new waitlist entry.

    Steps:
    1. Fetch RFPVenue and validate it's unavailable
    2. Check rate limit (max 5 active entries per organizer)
    3. Check for duplicate active entry for same venue
    4. Inherit all context from RFP
    5. Compute expires_at (30 days after desired_dates_end, or 90 days if flexible)
    6. Create entry with status="waiting"
    7. Emit Kafka event (handled by caller)
    """
    # Fetch RFPVenue with eager loading
    rfp_venue = (
        db.query(RFPVenue)
        .options(
            joinedload(RFPVenue.rfp),
            joinedload(RFPVenue.venue),
            joinedload(RFPVenue.response),
        )
        .filter(RFPVenue.id == rfp_venue_id)
        .first()
    )

    if not rfp_venue:
        raise HTTPException(status_code=404, detail="RFP venue not found")

    # Validate: must be unavailable
    if not rfp_venue.response or rfp_venue.response.availability != "unavailable":
        raise HTTPException(
            status_code=400,
            detail="Can only join waitlist for unavailable venues",
        )

    # Check rate limit
    active_count = count_active_entries(db, org_id)
    if active_count >= MAX_ACTIVE_WAITLIST_ENTRIES:
        raise HTTPException(
            status_code=429,
            detail="Maximum 5 active waitlist entries per organizer",
        )

    # Check for duplicate
    existing = (
        db.query(VenueWaitlistEntry)
        .filter(
            VenueWaitlistEntry.organization_id == org_id,
            VenueWaitlistEntry.venue_id == rfp_venue.venue_id,
            VenueWaitlistEntry.status.in_(ACTIVE_STATUSES),
        )
        .first()
    )

    if existing:
        raise HTTPException(
            status_code=409,
            detail="Already on waitlist for this venue",
        )

    rfp = rfp_venue.rfp

    # Inherit context from RFP
    desired_dates_start = rfp.preferred_dates_start
    desired_dates_end = rfp.preferred_dates_end
    dates_flexible = rfp.dates_flexible
    attendance_min = rfp.attendance_min
    attendance_max = rfp.attendance_max
    event_type = rfp.event_type
    space_requirements = rfp.space_requirements or []

    # Compute expires_at
    now = datetime.now(timezone.utc)
    if desired_dates_end and not dates_flexible:
        # 30 days after desired_dates_end
        expires_at = datetime.combine(
            desired_dates_end, datetime.min.time(), tzinfo=timezone.utc
        ) + timedelta(days=30)
    else:
        # 90 days from now
        expires_at = now + timedelta(days=90)

    # Create entry
    entry = VenueWaitlistEntry(
        organization_id=org_id,
        venue_id=rfp_venue.venue_id,
        source_rfp_id=rfp.id,
        source_rfp_venue_id=rfp_venue.id,
        desired_dates_start=desired_dates_start,
        desired_dates_end=desired_dates_end,
        dates_flexible=dates_flexible,
        attendance_min=attendance_min,
        attendance_max=attendance_max,
        event_type=event_type,
        space_requirements=space_requirements,
        status="waiting",
        expires_at=expires_at,
    )

    db.add(entry)
    db.commit()
    db.refresh(entry)

    logger.info(
        f"Created waitlist entry {entry.id} for org {org_id}, venue {rfp_venue.venue_id}"
    )

    return entry


def get_waitlist_entry(
    db: Session, *, entry_id: str, org_id: str
) -> Optional[VenueWaitlistEntry]:
    """Get single entry with org_id authorization check."""
    return (
        db.query(VenueWaitlistEntry)
        .options(
            joinedload(VenueWaitlistEntry.venue),
            joinedload(VenueWaitlistEntry.source_rfp),
        )
        .filter(
            VenueWaitlistEntry.id == entry_id,
            VenueWaitlistEntry.organization_id == org_id,
        )
        .first()
    )


def list_waitlist_entries(
    db: Session,
    *,
    org_id: str,
    status: Optional[str] = None,
    active_only: bool = False,
    page: int = 1,
    page_size: int = 10,
) -> dict:
    """Paginated list of waitlist entries for an organizer."""
    page_size = min(page_size, 50)
    query = db.query(VenueWaitlistEntry).filter(
        VenueWaitlistEntry.organization_id == org_id
    )

    if status:
        query = query.filter(VenueWaitlistEntry.status == status)
    elif active_only:
        query = query.filter(VenueWaitlistEntry.status.in_(ACTIVE_STATUSES))

    total_count = query.count()
    total_pages = math.ceil(total_count / page_size) if page_size > 0 else 0
    offset = (page - 1) * page_size

    entries = (
        query.options(
            joinedload(VenueWaitlistEntry.venue),
            joinedload(VenueWaitlistEntry.source_rfp),
        )
        .order_by(VenueWaitlistEntry.created_at.desc())
        .offset(offset)
        .limit(page_size)
        .all()
    )

    return {
        "entries": entries,
        "pagination": {
            "page": page,
            "page_size": page_size,
            "total_count": total_count,
            "total_pages": total_pages,
        },
    }


def get_queue_position(db: Session, *, entry: VenueWaitlistEntry) -> Optional[int]:
    """
    Calculate queue position for an entry.
    Returns None for terminal states (converted, expired, cancelled).
    """
    if entry.status in TERMINAL_STATUSES:
        return None

    position = (
        db.query(func.count(VenueWaitlistEntry.id))
        .filter(
            VenueWaitlistEntry.venue_id == entry.venue_id,
            VenueWaitlistEntry.status.in_(ACTIVE_STATUSES),
            VenueWaitlistEntry.created_at < entry.created_at,
        )
        .scalar()
    )

    return position + 1 if position is not None else 1


def cancel_entry(
    db: Session,
    *,
    entry: VenueWaitlistEntry,
    reason: str,
    notes: Optional[str] = None,
) -> VenueWaitlistEntry:
    """
    Cancel a waitlist entry.
    If was in 'offered' state, triggers cascade to next person.
    """
    if entry.status not in ACTIVE_STATUSES:
        raise HTTPException(
            status_code=422,
            detail="Can only cancel waiting or offered entries",
        )

    was_offered = entry.status == "offered"
    venue_id = entry.venue_id

    entry.status = "cancelled"
    entry.cancellation_reason = reason
    entry.cancellation_notes = notes

    db.commit()
    db.refresh(entry)

    logger.info(f"Cancelled waitlist entry {entry.id}, reason: {reason}")

    # If was offered, trigger cascade (handled by caller)
    if was_offered:
        logger.info(f"Entry was offered, will trigger cascade for venue {venue_id}")
        # Cascade logic is in app.utils.waitlist_cascade.trigger_cascade

    return entry


def convert_hold(db: Session, *, entry: VenueWaitlistEntry, org_id: str) -> dict:
    """
    Convert a hold into a new pre-filled RFP.

    Steps:
    1. Validate state (must be "offered")
    2. Validate hold not expired
    3. Check RFP rate limit (max 5 active RFPs)
    4. Clone source RFP (use duplicate_rfp logic)
    5. Target only the waitlisted venue
    6. Set response_deadline = now + 7 days
    7. Set converted_rfp_id
    8. Set status="converted"
    9. Emit Kafka event (handled by caller)
    """
    if entry.status != "offered":
        raise HTTPException(
            status_code=422,
            detail="Can only convert entries in 'offered' state",
        )

    now = datetime.now(timezone.utc)
    if entry.hold_expires_at and entry.hold_expires_at < now:
        raise HTTPException(
            status_code=422,
            detail="Hold has expired",
        )

    # Check RFP rate limit
    from app.crud import crud_rfp

    active_rfp_count = crud_rfp.count_active_rfps(db, org_id)
    if active_rfp_count >= MAX_ACTIVE_RFPS:
        raise HTTPException(
            status_code=429,
            detail="Maximum 5 active RFPs. Cannot convert hold.",
        )

    # Get source RFP
    source_rfp = db.query(RFP).filter(RFP.id == entry.source_rfp_id).first()
    if not source_rfp:
        raise HTTPException(status_code=404, detail="Source RFP not found")

    # Clone the RFP
    new_rfp = RFP(
        organization_id=org_id,
        title=source_rfp.title,
        event_type=source_rfp.event_type,
        attendance_min=source_rfp.attendance_min,
        attendance_max=source_rfp.attendance_max,
        preferred_dates_start=source_rfp.preferred_dates_start,
        preferred_dates_end=source_rfp.preferred_dates_end,
        dates_flexible=source_rfp.dates_flexible,
        duration=source_rfp.duration,
        space_requirements=source_rfp.space_requirements,
        required_amenity_ids=source_rfp.required_amenity_ids,
        catering_needs=source_rfp.catering_needs,
        budget_min=source_rfp.budget_min,
        budget_max=source_rfp.budget_max,
        budget_currency=source_rfp.budget_currency,
        preferred_currency=source_rfp.preferred_currency,
        additional_notes=source_rfp.additional_notes,
        response_deadline=now + timedelta(days=7),
        status="draft",
    )

    db.add(new_rfp)
    db.flush()  # Get ID for new RFP

    # Add ONLY the waitlisted venue
    from app.crud import crud_rfp_venue

    rfp_venue = RFPVenue(
        rfp_id=new_rfp.id,
        venue_id=entry.venue_id,
        status="received",
    )
    db.add(rfp_venue)

    # Update entry
    entry.status = "converted"
    entry.converted_rfp_id = new_rfp.id

    db.commit()
    db.refresh(entry)
    db.refresh(new_rfp)

    logger.info(
        f"Converted waitlist entry {entry.id} to new RFP {new_rfp.id}"
    )

    return {"waitlist_entry": entry, "new_rfp": new_rfp}


def get_next_waiting_entry(db: Session, *, venue_id: str) -> Optional[VenueWaitlistEntry]:
    """Find first entry with status='waiting' for this venue, ordered by created_at ASC."""
    return (
        db.query(VenueWaitlistEntry)
        .filter(
            VenueWaitlistEntry.venue_id == venue_id,
            VenueWaitlistEntry.status == "waiting",
        )
        .order_by(VenueWaitlistEntry.created_at.asc())
        .first()
    )


def offer_hold(db: Session, *, entry: VenueWaitlistEntry) -> VenueWaitlistEntry:
    """
    Offer a hold to an entry.
    Sets status='offered', hold_offered_at=now, hold_expires_at=now+48h.
    """
    now = datetime.now(timezone.utc)
    entry.status = "offered"
    entry.hold_offered_at = now
    entry.hold_expires_at = now + timedelta(hours=48)

    db.commit()
    db.refresh(entry)

    logger.info(f"Offered hold to waitlist entry {entry.id}")

    return entry


def expire_hold(db: Session, *, entry: VenueWaitlistEntry) -> VenueWaitlistEntry:
    """Expire a hold (set status='expired')."""
    entry.status = "expired"
    db.commit()
    db.refresh(entry)

    logger.info(f"Expired hold for waitlist entry {entry.id}")

    return entry


def get_consecutive_no_responses(db: Session, *, venue_id: str) -> int:
    """
    Count consecutive expired entries (not cancelled) at the front of the queue.
    This is used for the circuit breaker logic (3+ consecutive = pause).
    """
    # Get all terminal entries for this venue, ordered by created_at DESC
    entries = (
        db.query(VenueWaitlistEntry)
        .filter(
            VenueWaitlistEntry.venue_id == venue_id,
            VenueWaitlistEntry.status.in_(TERMINAL_STATUSES),
        )
        .order_by(VenueWaitlistEntry.created_at.desc())
        .all()
    )

    count = 0
    for entry in entries:
        if entry.status == "expired":
            count += 1
        else:
            # Hit a non-expired terminal entry, stop counting
            break

    return count


def resolve_circuit_breaker(db: Session, *, venue_id: str) -> dict:
    """
    Venue owner confirms the waitlist should remain active after circuit breaker pause.

    Steps:
    1. Validate venue has active circuit breaker (3+ consecutive no-responses)
    2. Reset counter (this happens automatically by offering to next person)
    3. Trigger cascade
    4. Emit Kafka event (handled by caller)
    """
    consecutive = get_consecutive_no_responses(db, venue_id=venue_id)
    if consecutive < 3:
        raise HTTPException(
            status_code=400,
            detail="No active circuit breaker for this venue",
        )

    # Circuit breaker is active, proceed with resolution
    # The cascade will reset the counter by offering to next person
    logger.info(f"Resolving circuit breaker for venue {venue_id}, consecutive={consecutive}")

    return {"venue_id": venue_id, "consecutive_no_responses": consecutive}
