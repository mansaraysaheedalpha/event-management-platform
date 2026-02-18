# app/background_tasks/venue_waitlist_tasks.py
"""
Background jobs for venue waitlist processing.

All jobs use APScheduler (NOT Celery).
Registered in app/scheduler.py.
"""
import logging
from datetime import datetime, timezone, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.models.venue_waitlist_entry import VenueWaitlistEntry
from app.crud import crud_venue_waitlist
from app.utils.waitlist_cascade import trigger_cascade
from app.utils import venue_waitlist_notifications
from app.utils.venue_availability_inference import run_inference_all
from app.utils.kafka_helpers import get_kafka_singleton

logger = logging.getLogger(__name__)

# Create a separate DB session for background tasks
engine = create_engine(settings.DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def process_hold_expiry():
    """
    Process expired holds.
    Schedule: Every 1 minute

    Steps:
    1. Find entries where status='offered' AND hold_expires_at < now()
    2. For each entry:
       a. Expire the hold (set status='expired')
       b. Increment consecutive_no_responses counter
       c. Check circuit breaker (>= 3)
       d. If circuit breaker, notify venue owner and stop
       e. Otherwise, trigger cascade to next person
    """
    logger.info("Running process_hold_expiry job")
    db = SessionLocal()

    try:
        now = datetime.now(timezone.utc)

        expired_entries = (
            db.query(VenueWaitlistEntry)
            .filter(
                VenueWaitlistEntry.status == "offered",
                VenueWaitlistEntry.hold_expires_at < now,
            )
            .all()
        )

        logger.info(f"Found {len(expired_entries)} expired holds")

        for entry in expired_entries:
            venue_id = entry.venue_id

            # Expire the hold
            crud_venue_waitlist.expire_hold(db, entry=entry)

            # Send notification
            try:
                venue_waitlist_notifications.notify_hold_expired(entry)
            except Exception as e:
                logger.error(f"Failed to send hold expired notification: {e}")

            # Trigger cascade (cascade logic handles circuit breaker internally)
            trigger_cascade(db, venue_id)

    except Exception as e:
        logger.error(f"Error in process_hold_expiry: {e}", exc_info=True)
    finally:
        db.close()


def send_hold_reminders():
    """
    Send 24h-before reminders for active holds.
    Schedule: Every 15 minutes

    Find entries where:
    - status='offered'
    - hold_expires_at - now() < 24h
    - hold_reminder_sent = False
    """
    logger.info("Running send_hold_reminders job")
    db = SessionLocal()

    try:
        now = datetime.now(timezone.utc)
        reminder_threshold = now + timedelta(hours=24)

        entries_needing_reminder = (
            db.query(VenueWaitlistEntry)
            .filter(
                VenueWaitlistEntry.status == "offered",
                VenueWaitlistEntry.hold_expires_at <= reminder_threshold,
                VenueWaitlistEntry.hold_reminder_sent == False,
            )
            .all()
        )

        logger.info(f"Found {len(entries_needing_reminder)} holds needing reminders")

        for entry in entries_needing_reminder:
            try:
                venue_waitlist_notifications.notify_hold_reminder(entry)

                # Mark reminder as sent
                entry.hold_reminder_sent = True
                db.commit()

            except Exception as e:
                logger.error(f"Failed to send hold reminder for entry {entry.id}: {e}")

    except Exception as e:
        logger.error(f"Error in send_hold_reminders: {e}", exc_info=True)
    finally:
        db.close()


def process_auto_expiry():
    """
    Auto-expire entries that have passed their expiry date.
    Schedule: Every 1 hour

    Find entries where:
    - status='waiting'
    - expires_at < now()
    """
    logger.info("Running process_auto_expiry job")
    db = SessionLocal()

    try:
        now = datetime.now(timezone.utc)

        entries_to_expire = (
            db.query(VenueWaitlistEntry)
            .filter(
                VenueWaitlistEntry.status == "waiting",
                VenueWaitlistEntry.expires_at < now,
            )
            .all()
        )

        logger.info(f"Found {len(entries_to_expire)} entries to auto-expire")

        for entry in entries_to_expire:
            entry.status = "expired"
            db.commit()

            try:
                venue_waitlist_notifications.notify_auto_expired(entry)
            except Exception as e:
                logger.error(f"Failed to send auto-expired notification: {e}")

    except Exception as e:
        logger.error(f"Error in process_auto_expiry: {e}", exc_info=True)
    finally:
        db.close()


def send_still_interested_nudges():
    """
    Send "still interested?" nudges for general entries at 60 days.
    Schedule: Daily at 10:00 UTC

    Find entries where:
    - status='waiting'
    - dates_flexible=True (general entries)
    - created_at + 60 days < now()
    - still_interested_sent_at IS NULL
    """
    logger.info("Running send_still_interested_nudges job")
    db = SessionLocal()

    try:
        now = datetime.now(timezone.utc)
        sixty_days_ago = now - timedelta(days=60)

        entries_needing_nudge = (
            db.query(VenueWaitlistEntry)
            .filter(
                VenueWaitlistEntry.status == "waiting",
                VenueWaitlistEntry.dates_flexible == True,
                VenueWaitlistEntry.created_at <= sixty_days_ago,
                VenueWaitlistEntry.still_interested_sent_at == None,
            )
            .all()
        )

        logger.info(f"Found {len(entries_needing_nudge)} entries needing nudge")

        for entry in entries_needing_nudge:
            try:
                venue_waitlist_notifications.notify_still_interested(entry)

                # Mark nudge as sent
                entry.still_interested_sent_at = now
                db.commit()

            except Exception as e:
                logger.error(f"Failed to send still interested nudge for entry {entry.id}: {e}")

    except Exception as e:
        logger.error(f"Error in send_still_interested_nudges: {e}", exc_info=True)
    finally:
        db.close()


def process_nudge_expiry():
    """
    Expire entries where nudge was sent 7+ days ago with no response.
    Schedule: Daily at 10:00 UTC

    Find entries where:
    - still_interested_sent_at + 7 days < now()
    - still_interested_responded = False
    """
    logger.info("Running process_nudge_expiry job")
    db = SessionLocal()

    try:
        now = datetime.now(timezone.utc)
        seven_days_ago = now - timedelta(days=7)

        entries_to_expire = (
            db.query(VenueWaitlistEntry)
            .filter(
                VenueWaitlistEntry.still_interested_sent_at <= seven_days_ago,
                VenueWaitlistEntry.still_interested_responded == False,
                VenueWaitlistEntry.status == "waiting",  # Only expire active waiting entries
            )
            .all()
        )

        logger.info(f"Found {len(entries_to_expire)} entries to expire due to no nudge response")

        for entry in entries_to_expire:
            entry.status = "expired"
            entry.cancellation_reason = "nudge_declined"
            db.commit()

            try:
                venue_waitlist_notifications.notify_auto_expired(entry)
            except Exception as e:
                logger.error(f"Failed to send nudge expiry notification: {e}")

    except Exception as e:
        logger.error(f"Error in process_nudge_expiry: {e}", exc_info=True)
    finally:
        db.close()


def run_availability_inference():
    """
    Run the signal-driven availability inference engine for all venues.
    Schedule: Every 6 hours

    Calls the inference engine which:
    1. Analyzes signals from last 90 days
    2. Computes availability status
    3. Updates venue.availability_status (if no manual override)
    4. Triggers cascade if status improved
    """
    logger.info("Running run_availability_inference job")
    db = SessionLocal()

    try:
        changes = run_inference_all(db)
        logger.info(f"Inference complete: {len(changes)} venues changed status")

        for venue_id, (old, new) in changes.items():
            logger.info(f"Venue {venue_id}: {old} → {new}")

    except Exception as e:
        logger.error(f"Error in run_availability_inference: {e}", exc_info=True)
    finally:
        db.close()


def process_circuit_breaker_expiry():
    """
    Deactivate waitlists where circuit breaker was triggered 7+ days ago with no resolution.
    Schedule: Daily at 00:00 UTC

    This is a safety mechanism — if venue owner doesn't respond to circuit breaker
    notification for 7 days, we assume the waitlist is no longer active.

    Steps:
    1. Find venues with circuit breaker active (>= 3 consecutive no-responses)
    2. Check if any entries have been waiting 7+ days since the last expired hold
    3. If so, cancel all remaining "waiting" entries with reason "circuit_breaker_timeout"
    4. Notify affected organizers
    """
    logger.info("Running process_circuit_breaker_expiry job")
    db = SessionLocal()

    try:
        now = datetime.now(timezone.utc)
        seven_days_ago = now - timedelta(days=7)

        # Get venues that have waitlist entries
        venues_with_waitlists = (
            db.query(VenueWaitlistEntry.venue_id)
            .filter(VenueWaitlistEntry.status.in_(["waiting", "expired"]))
            .distinct()
            .all()
        )

        for (venue_id,) in venues_with_waitlists:
            # Check if circuit breaker is active for this venue
            consecutive = crud_venue_waitlist.get_consecutive_no_responses(db, venue_id=venue_id)

            if consecutive < 3:
                continue  # No circuit breaker for this venue

            # Get the last expired entry to check when circuit breaker triggered
            last_expired = (
                db.query(VenueWaitlistEntry)
                .filter(
                    VenueWaitlistEntry.venue_id == venue_id,
                    VenueWaitlistEntry.status == "expired",
                    VenueWaitlistEntry.hold_expires_at.isnot(None),
                )
                .order_by(VenueWaitlistEntry.hold_expires_at.desc())
                .first()
            )

            if not last_expired:
                continue

            # Check if 7+ days have passed since the last expired hold
            if last_expired.hold_expires_at and last_expired.hold_expires_at < seven_days_ago:
                # Circuit breaker has been active for 7+ days with no resolution
                # Cancel all remaining waiting entries
                waiting_entries = (
                    db.query(VenueWaitlistEntry)
                    .filter(
                        VenueWaitlistEntry.venue_id == venue_id,
                        VenueWaitlistEntry.status == "waiting",
                    )
                    .all()
                )

                logger.info(
                    f"Circuit breaker timeout for venue {venue_id}: "
                    f"cancelling {len(waiting_entries)} waiting entries"
                )

                for entry in waiting_entries:
                    entry.status = "cancelled"
                    entry.cancellation_reason = "circuit_breaker_timeout"
                    entry.cancellation_notes = (
                        "Waitlist deactivated after 7 days of circuit breaker inactivity. "
                        "The venue owner did not respond to the circuit breaker notification."
                    )
                    db.commit()

                    # Notify organizer
                    try:
                        venue_waitlist_notifications.notify_auto_expired(entry)
                    except Exception as e:
                        logger.error(
                            f"Failed to send circuit breaker timeout notification for entry {entry.id}: {e}"
                        )

                # Also set venue availability to "not_set" as a safety measure
                from app.models.venue import Venue
                venue = db.query(Venue).filter(Venue.id == venue_id).first()
                if venue and venue.availability_status == "accepting_events":
                    venue.availability_status = "not_set"
                    venue.availability_manual_override_at = now
                    db.commit()
                    logger.info(
                        f"Reset availability status for venue {venue_id} due to circuit breaker timeout"
                    )

    except Exception as e:
        logger.error(f"Error in process_circuit_breaker_expiry: {e}", exc_info=True)
    finally:
        db.close()
