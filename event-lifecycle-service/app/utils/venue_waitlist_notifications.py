# app/utils/venue_waitlist_notifications.py
"""
Multi-channel notification dispatchers for waitlist events.

Channels: In-app + Email + WhatsApp (where applicable)
Follows patterns from app/utils/rfp_notifications.py
"""
import logging
from typing import Optional
from datetime import datetime, timezone

from app.models.venue_waitlist_entry import VenueWaitlistEntry
from app.utils.kafka_helpers import get_kafka_singleton

logger = logging.getLogger(__name__)


def notify_waitlist_joined(entry: VenueWaitlistEntry):
    """
    Notify organizer that they've joined a waitlist.
    Channels: In-app + Email
    """
    logger.info(f"Sending waitlist joined notification for entry {entry.id}")

    # TODO: Implement in-app notification
    # TODO: Implement email notification
    # Confirmation with queue position

    _emit_kafka("waitlist.joined_notification", entry)


def notify_hold_offered(entry: VenueWaitlistEntry):
    """
    Notify organizer that a hold has been offered (their turn in queue).
    Channels: In-app + Email + WhatsApp
    WhatsApp template: waitlist_hold_offered
    """
    logger.info(f"Sending hold offered notification for entry {entry.id}")

    # TODO: Implement in-app notification
    # TODO: Implement email notification
    # TODO: Implement WhatsApp notification using template 'waitlist_hold_offered'

    _emit_kafka("waitlist.hold_offered_notification", entry)


def notify_hold_reminder(entry: VenueWaitlistEntry):
    """
    Send 24h reminder before hold expires.
    Channels: Email + WhatsApp
    WhatsApp template: waitlist_hold_reminder
    """
    logger.info(f"Sending hold reminder for entry {entry.id}")

    # TODO: Implement email notification
    # TODO: Implement WhatsApp notification using template 'waitlist_hold_reminder'

    _emit_kafka("waitlist.hold_reminder_notification", entry)


def notify_hold_expired(entry: VenueWaitlistEntry):
    """
    Notify organizer that hold expired without action.
    Channels: In-app + Email
    """
    logger.info(f"Sending hold expired notification for entry {entry.id}")

    # TODO: Implement in-app notification
    # TODO: Implement email notification

    _emit_kafka("waitlist.hold_expired_notification", entry)


def notify_converted(entry: VenueWaitlistEntry):
    """
    Notify organizer of successful conversion to new RFP.
    Channels: In-app
    """
    logger.info(f"Sending conversion notification for entry {entry.id}")

    # TODO: Implement in-app notification with link to new RFP

    _emit_kafka("waitlist.converted_notification", entry)


def notify_position_changed(entry: VenueWaitlistEntry, new_position: int):
    """
    Notify organizer that queue position improved.
    Channels: In-app
    """
    logger.info(
        f"Sending position changed notification for entry {entry.id}, new position: {new_position}"
    )

    # TODO: Implement in-app notification

    _emit_kafka(
        "waitlist.position_changed_notification", entry, {"new_position": new_position}
    )


def notify_still_interested(entry: VenueWaitlistEntry):
    """
    Send "still interested?" nudge at 60 days.
    Channels: Email
    """
    logger.info(f"Sending still interested nudge for entry {entry.id}")

    # TODO: Implement email with action link

    _emit_kafka("waitlist.still_interested_nudge", entry)


def notify_auto_expired(entry: VenueWaitlistEntry):
    """
    Notify organizer that entry auto-expired.
    Channels: In-app + Email
    """
    logger.info(f"Sending auto-expired notification for entry {entry.id}")

    # TODO: Implement in-app notification
    # TODO: Implement email notification

    _emit_kafka("waitlist.auto_expired_notification", entry)


def notify_circuit_breaker(venue_id: str):
    """
    Notify venue owner that circuit breaker was triggered.
    Channels: In-app + Email
    """
    logger.info(f"Sending circuit breaker notification for venue {venue_id}")

    # TODO: Implement in-app notification to venue owner
    # TODO: Implement email notification to venue owner

    try:
        producer = get_kafka_singleton()
        if producer:
            event_data = {
                "type": "WAITLIST_CIRCUIT_BREAKER",
                "venue_id": venue_id,
                "timestamp": str(datetime.now(timezone.utc)),
            }
            producer.send("waitlist-events", value=event_data)
    except Exception as e:
        logger.error(f"Failed to emit circuit breaker Kafka event: {e}")


def notify_circuit_breaker_resolved(venue_id: str):
    """
    Notify venue owner that circuit breaker was resolved.
    Channels: In-app + Email
    """
    logger.info(f"Sending circuit breaker resolved notification for venue {venue_id}")

    # TODO: Implement in-app notification
    # TODO: Implement email notification

    try:
        producer = get_kafka_singleton()
        if producer:
            event_data = {
                "type": "WAITLIST_CIRCUIT_BREAKER_RESOLVED",
                "venue_id": venue_id,
                "timestamp": str(datetime.now(timezone.utc)),
            }
            producer.send("waitlist-events", value=event_data)
    except Exception as e:
        logger.error(f"Failed to emit circuit breaker resolved Kafka event: {e}")


# Helper functions


def _emit_kafka(event_type: str, entry: VenueWaitlistEntry, metadata: dict = None):
    """Emit Kafka event for notification tracking."""
    try:
        producer = get_kafka_singleton()
        if not producer:
            logger.warning("Kafka producer unavailable, skipping event")
            return

        event_data = {
            "type": event_type,
            "waitlist_entry_id": entry.id,
            "organization_id": entry.organization_id,
            "venue_id": entry.venue_id,
            "status": entry.status,
            "metadata": metadata or {},
            "timestamp": str(datetime.now(timezone.utc)),
        }

        producer.send("waitlist-events", value=event_data)
        logger.debug(f"Emitted Kafka event: {event_type} for entry {entry.id}")
    except Exception as e:
        logger.error(f"Failed to emit Kafka event {event_type}: {e}")
