# app/crud/crud_venue_availability.py
import logging
from typing import Optional
from datetime import datetime, timezone, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import func
from fastapi import HTTPException

from app.models.venue import Venue
from app.models.venue_availability_signal import VenueAvailabilitySignal
from app.models.venue_waitlist_entry import VenueWaitlistEntry

logger = logging.getLogger(__name__)


def get_venue_availability(db: Session, *, venue_id: str) -> dict:
    """
    Get venue's current availability status and inference data.
    Returns summary with status, override info, and signal summary.
    """
    venue = db.query(Venue).filter(Venue.id == venue_id).first()
    if not venue:
        raise HTTPException(status_code=404, detail="Venue not found")

    # Get signal summary
    signal_summary = get_signal_summary(db, venue_id=venue_id, days=90)

    # Check if manual override is active
    is_manual_override = False
    if venue.availability_manual_override_at:
        # Manual override is active if it's more recent than last inference
        if not venue.availability_last_inferred_at or \
           venue.availability_manual_override_at > venue.availability_last_inferred_at:
            is_manual_override = True

    return {
        "venue_id": venue_id,
        "availability_status": venue.availability_status or "not_set",
        "is_manual_override": is_manual_override,
        "last_inferred_at": venue.availability_last_inferred_at,
        "inferred_status": venue.availability_inferred_status,
        "manual_override_at": venue.availability_manual_override_at,
        "signal_summary": signal_summary,
    }


def set_venue_availability(
    db: Session, *, venue_id: str, org_id: str, status: str
) -> Venue:
    """
    Manually set venue availability status.
    This creates a manual override that takes precedence over inference.

    If new status is "accepting_events" and venue has waitlist entries,
    triggers cascade (handled by caller).
    """
    venue = db.query(Venue).filter(Venue.id == venue_id).first()
    if not venue:
        raise HTTPException(status_code=404, detail="Venue not found")

    # Verify venue ownership
    if venue.organization_id != org_id:
        raise HTTPException(status_code=403, detail="Not authorized")

    now = datetime.now(timezone.utc)
    venue.availability_status = status
    venue.availability_manual_override_at = now

    db.commit()
    db.refresh(venue)

    logger.info(
        f"Venue {venue_id} availability manually set to {status} by org {org_id}"
    )

    # Check if we should trigger cascade
    if status == "accepting_events":
        has_waitlist = (
            db.query(VenueWaitlistEntry)
            .filter(
                VenueWaitlistEntry.venue_id == venue_id,
                VenueWaitlistEntry.status == "waiting",
            )
            .first()
        )
        if has_waitlist:
            logger.info(f"Venue {venue_id} has waitlist entries, will trigger cascade")
            # Cascade logic is handled by caller

    return venue


def clear_manual_override(db: Session, *, venue_id: str, org_id: str) -> Venue:
    """
    Clear the manual override, returning to inference-driven status.
    """
    venue = db.query(Venue).filter(Venue.id == venue_id).first()
    if not venue:
        raise HTTPException(status_code=404, detail="Venue not found")

    # Verify venue ownership
    if venue.organization_id != org_id:
        raise HTTPException(status_code=403, detail="Not authorized")

    venue.availability_manual_override_at = None

    # Revert to inferred status if available
    if venue.availability_inferred_status:
        venue.availability_status = venue.availability_inferred_status
    else:
        venue.availability_status = "not_set"

    db.commit()
    db.refresh(venue)

    logger.info(f"Venue {venue_id} manual override cleared, reverted to inferred status")

    return venue


def record_signal(
    db: Session,
    *,
    venue_id: str,
    signal_type: str,
    source_rfp_id: Optional[str] = None,
    source_rfp_venue_id: Optional[str] = None,
    signal_date: Optional[str] = None,
    metadata: Optional[dict] = None,
) -> VenueAvailabilitySignal:
    """
    Append a new availability signal to the audit log.
    This is called from RFP lifecycle events.
    """
    signal = VenueAvailabilitySignal(
        venue_id=venue_id,
        signal_type=signal_type,
        source_rfp_id=source_rfp_id,
        source_rfp_venue_id=source_rfp_venue_id,
        signal_date=signal_date,
        metadata=metadata,
    )

    db.add(signal)
    db.commit()
    db.refresh(signal)

    logger.info(f"Recorded signal {signal_type} for venue {venue_id}")

    return signal


def get_signal_summary(db: Session, *, venue_id: str, days: int = 90) -> dict:
    """
    Count signals by type for the last N days.
    Returns summary with ratios for inference display.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    signals = (
        db.query(VenueAvailabilitySignal)
        .filter(
            VenueAvailabilitySignal.venue_id == venue_id,
            VenueAvailabilitySignal.recorded_at >= cutoff,
            VenueAvailabilitySignal.signal_type.in_(
                ["confirmed", "tentative", "unavailable"]
            ),
        )
        .all()
    )

    total = len(signals)
    confirmed_count = sum(1 for s in signals if s.signal_type == "confirmed")
    tentative_count = sum(1 for s in signals if s.signal_type == "tentative")
    unavailable_count = sum(1 for s in signals if s.signal_type == "unavailable")

    unavailable_ratio = unavailable_count / total if total > 0 else 0.0

    return {
        "period_days": days,
        "total_responses": total,
        "confirmed_count": confirmed_count,
        "tentative_count": tentative_count,
        "unavailable_count": unavailable_count,
        "unavailable_ratio": round(unavailable_ratio, 2),
    }
