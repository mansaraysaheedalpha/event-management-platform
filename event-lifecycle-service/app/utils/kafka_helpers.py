# app/utils/kafka_helpers.py
"""
Kafka helper functions for publishing events to topics.
Supports SASL_SSL authentication for Confluent Cloud.
"""
import json
import logging
from kafka import KafkaProducer
from kafka.errors import NoBrokersAvailable
from app.core.config import settings

logger = logging.getLogger(__name__)

# Kafka Topics
TOPIC_WAITLIST_EVENTS = "waitlist.events.v1"


def get_kafka_producer() -> KafkaProducer | None:
    """
    Get a Kafka producer instance with SASL authentication support.

    Returns:
        KafkaProducer configured for the platform, or None if unavailable
    """
    if not settings.KAFKA_BOOTSTRAP_SERVERS:
        logger.warning("Kafka bootstrap servers not configured")
        return None

    try:
        # Base configuration
        kafka_config = {
            "bootstrap_servers": settings.KAFKA_BOOTSTRAP_SERVERS,
            "value_serializer": lambda v: json.dumps(v).encode('utf-8'),
            "request_timeout_ms": 10000,
        }

        # Add SASL authentication if credentials are provided (for Confluent Cloud)
        if settings.KAFKA_API_KEY and settings.KAFKA_API_SECRET:
            kafka_config.update({
                "security_protocol": settings.KAFKA_SECURITY_PROTOCOL or "SASL_SSL",
                "sasl_mechanism": settings.KAFKA_SASL_MECHANISM or "PLAIN",
                "sasl_plain_username": settings.KAFKA_API_KEY,
                "sasl_plain_password": settings.KAFKA_API_SECRET,
            })

        return KafkaProducer(**kafka_config)

    except (NoBrokersAvailable, Exception) as e:
        logger.error(f"Failed to create Kafka producer: {e}")
        return None


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
    producer = None
    try:
        producer = get_kafka_producer()

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

    finally:
        if producer:
            producer.close()
