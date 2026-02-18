# app/utils/waitlist_cascade.py
"""
Waitlist cascade logic — offers hold to the next person in FIFO queue.

This is the core mechanism for managing the waitlist queue flow.
"""
import logging
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


def trigger_cascade(db: Session, venue_id: str):
    """
    Offer hold to next person in FIFO queue.

    Steps:
    1. Check circuit breaker (3+ consecutive no-responses)
    2. If circuit breaker active, notify venue owner and stop
    3. Otherwise, get next waiting entry
    4. Offer hold to that entry
    5. Send multi-channel notification
    6. Emit Kafka event
    """
    from app.crud import crud_venue_waitlist
    from app.utils.kafka_helpers import get_kafka_singleton

    # Check circuit breaker
    consecutive = crud_venue_waitlist.get_consecutive_no_responses(
        db, venue_id=venue_id
    )

    if consecutive >= 3:
        # Circuit breaker active — notify venue owner, don't cascade
        logger.warning(
            f"Circuit breaker active for venue {venue_id}, "
            f"consecutive no-responses: {consecutive}"
        )

        # Emit Kafka event
        try:
            producer = get_kafka_singleton()
            if producer:
                event_data = {
                    "event_type": "waitlist.circuit_breaker_triggered",
                    "venue_id": venue_id,
                    "consecutive_no_responses": consecutive,
                    "timestamp": str(db.execute("SELECT NOW()").scalar()),
                }
                producer.send("waitlist-events", value=event_data)
        except Exception as e:
            logger.error(f"Failed to emit circuit breaker Kafka event: {e}")

        # Notify venue owner (handled by background job or notification service)
        from app.utils import venue_waitlist_notifications

        try:
            venue_waitlist_notifications.notify_circuit_breaker(venue_id)
        except Exception as e:
            logger.error(f"Failed to send circuit breaker notification: {e}")

        return

    # Get next waiting entry
    next_entry = crud_venue_waitlist.get_next_waiting_entry(db, venue_id=venue_id)

    if not next_entry:
        logger.info(f"No waiting entries for venue {venue_id}, cascade complete")
        return  # Queue empty

    # Offer hold
    crud_venue_waitlist.offer_hold(db, entry=next_entry)

    # Send notification (multi-channel: in-app + email + WhatsApp)
    from app.utils import venue_waitlist_notifications

    try:
        venue_waitlist_notifications.notify_hold_offered(next_entry)
    except Exception as e:
        logger.error(f"Failed to send hold offered notification: {e}")

    # Emit Kafka event
    try:
        producer = get_kafka_singleton()
        if producer:
            event_data = {
                "event_type": "waitlist.hold_offered",
                "waitlist_entry_id": next_entry.id,
                "venue_id": next_entry.venue_id,
                "organization_id": next_entry.organization_id,
                "source_rfp_id": next_entry.source_rfp_id,
                "previous_status": "waiting",
                "new_status": "offered",
                "metadata": {
                    "queue_position": 1,  # They're now #1 (being offered)
                    "hold_expires_at": str(next_entry.hold_expires_at),
                },
                "timestamp": str(next_entry.hold_offered_at),
            }
            producer.send("waitlist-events", value=event_data)
            logger.info(f"Emitted hold offered event for entry {next_entry.id}")
    except Exception as e:
        logger.error(f"Failed to emit hold offered Kafka event: {e}")

    logger.info(
        f"Cascade complete: offered hold to entry {next_entry.id} for venue {venue_id}"
    )
