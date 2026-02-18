# app/utils/venue_availability_inference.py
"""
Availability inference engine — analyzes signals and infers venue availability status.

Algorithm (from spec Section 5.2):
1. Query signals from last 90 days (signal_type in confirmed, tentative, unavailable)
2. If no signals: return "not_set"
3. Calculate unavailable_ratio = unavailable_count / total
4. If ratio >= 0.8: "fully_booked"
5. If ratio >= 0.5: "limited_availability"
6. Else: "accepting_events"

Never infer "seasonal" — that's manual only.
"""
import logging
from typing import Optional
from datetime import datetime, timezone, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models.venue import Venue
from app.models.venue_availability_signal import VenueAvailabilitySignal
from app.models.venue_waitlist_entry import VenueWaitlistEntry
from app.utils.kafka_helpers import get_kafka_singleton

logger = logging.getLogger(__name__)


def run_inference_for_venue(db: Session, venue_id: str) -> Optional[str]:
    """
    Run availability inference for a single venue.
    Returns the inferred status or None if insufficient data.
    """
    ninety_days_ago = datetime.now(timezone.utc) - timedelta(days=90)

    signals = (
        db.query(VenueAvailabilitySignal)
        .filter(
            VenueAvailabilitySignal.venue_id == venue_id,
            VenueAvailabilitySignal.recorded_at >= ninety_days_ago,
            VenueAvailabilitySignal.signal_type.in_(
                ["confirmed", "tentative", "unavailable"]
            ),
        )
        .all()
    )

    if not signals:
        return None  # not_set

    unavailable_count = sum(1 for s in signals if s.signal_type == "unavailable")
    total = len(signals)
    unavailable_ratio = unavailable_count / total

    if unavailable_ratio >= 0.8:
        return "fully_booked"
    elif unavailable_ratio >= 0.5:
        return "limited_availability"
    else:
        return "accepting_events"


def run_inference_all(db: Session) -> dict:
    """
    Run inference for all venues with recent signals.
    Called by the periodic background job.

    Returns dict of {venue_id: (old_status, new_status)} for venues that changed.

    For each venue where status improved AND manual override is NOT active:
      - Update venue.availability_status
      - Update venue.availability_last_inferred_at
      - Update venue.availability_inferred_status
      - Check if venue has waitlist entries → trigger cascade
    """
    ninety_days_ago = datetime.now(timezone.utc) - timedelta(days=90)
    now = datetime.now(timezone.utc)

    # Get all venues with recent signals
    venue_ids = (
        db.query(VenueAvailabilitySignal.venue_id)
        .filter(VenueAvailabilitySignal.recorded_at >= ninety_days_ago)
        .distinct()
        .all()
    )

    changes = {}

    for (venue_id,) in venue_ids:
        venue = db.query(Venue).filter(Venue.id == venue_id).first()
        if not venue:
            continue

        old_status = venue.availability_status
        new_status = run_inference_for_venue(db, venue_id)

        if new_status is None:
            continue

        # Store inferred status
        venue.availability_inferred_status = new_status
        venue.availability_last_inferred_at = now

        # Check if manual override is active
        manual_override_active = False
        if venue.availability_manual_override_at:
            if (
                not venue.availability_last_inferred_at
                or venue.availability_manual_override_at
                > venue.availability_last_inferred_at
            ):
                manual_override_active = True

        # Only UPDATE displayed status if no manual override
        if not manual_override_active:
            if new_status != old_status:
                venue.availability_status = new_status
                changes[venue_id] = (old_status, new_status)

                logger.info(
                    f"Venue {venue_id} availability inferred: {old_status} → {new_status}"
                )

                # If status IMPROVED and venue has waitlist entries, trigger cascade
                if _status_improved(old_status, new_status):
                    has_waitlist = (
                        db.query(VenueWaitlistEntry)
                        .filter(
                            VenueWaitlistEntry.venue_id == venue_id,
                            VenueWaitlistEntry.status == "waiting",
                        )
                        .first()
                    )

                    if has_waitlist:
                        logger.info(
                            f"Venue {venue_id} status improved, triggering cascade"
                        )
                        from app.utils.waitlist_cascade import trigger_cascade

                        trigger_cascade(db, venue_id)

    db.commit()

    # Emit Kafka events for all changes
    for venue_id, (old, new) in changes.items():
        try:
            producer = get_kafka_singleton()
            if producer:
                event_data = {
                    "event_type": "venue.availability_inferred",
                    "venue_id": venue_id,
                    "old_status": old,
                    "new_status": new,
                    "timestamp": str(now),
                }
                producer.send("waitlist-events", value=event_data)
        except Exception as e:
            logger.error(f"Failed to emit Kafka event for venue {venue_id}: {e}")

    logger.info(f"Inference complete: {len(changes)} venues changed status")
    return changes


def _status_improved(old: str, new: str) -> bool:
    """Check if availability improved (more available)."""
    ranking = {
        "fully_booked": 0,
        "limited_availability": 1,
        "accepting_events": 2,
        "seasonal": 1,  # seasonal is treated as limited
        "not_set": -1,
    }
    return ranking.get(new, -1) > ranking.get(old, -1)
