# app/utils/kafka_helpers.py
"""
Kafka helper functions for publishing events to topics.
Uses the singleton producer from app.core.kafka_producer.
"""
import logging
from app.core.kafka_producer import get_kafka_singleton

logger = logging.getLogger(__name__)

# Kafka Topics
TOPIC_WAITLIST_EVENTS = "waitlist.events.v1"


def publish_waitlist_offer_event(
    user_id: str,
    user_email: str,
    user_name: str,
    session_id: str,
    session_title: str,
    event_id: str,
    event_name: str,
    offer_token: str,
    offer_expires_at: str,
    position: int = None,
) -> bool:
    """
    Publish a waitlist offer event to Kafka.

    This event will be consumed by the email service to send the offer notification.

    Args:
        user_id: User's ID
        user_email: User's email address
        user_name: User's name
        session_id: Session ID
        session_title: Session title
        event_id: Event ID
        event_name: Event name
        offer_token: JWT token for accepting the offer
        offer_expires_at: ISO datetime string when offer expires
        position: Optional user's position in queue

    Returns:
        bool: True if published successfully, False otherwise
    """
    try:
        producer = get_kafka_singleton()

        if producer is None:
            logger.warning("Kafka producer unavailable, skipping event publish")
            return False

        event_data = {
            "type": "WAITLIST_OFFER",
            "userId": user_id,
            "userEmail": user_email,
            "userName": user_name,
            "sessionId": session_id,
            "sessionTitle": session_title,
            "eventId": event_id,
            "eventName": event_name,
            "offerToken": offer_token,
            "offerExpiresAt": offer_expires_at,
            "position": position,
        }

        future = producer.send(TOPIC_WAITLIST_EVENTS, value=event_data)
        # Wait for the send to complete (with timeout)
        future.get(timeout=10)

        logger.info(f"Published waitlist offer event for user {user_id}, session {session_id}")
        return True

    except Exception as e:
        logger.error(f"Failed to publish waitlist offer event: {e}", exc_info=True)
        return False