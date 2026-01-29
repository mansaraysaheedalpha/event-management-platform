#!/usr/bin/env python3
"""
Lead Capture Consumer Service

Listens for lead capture events from real-time-service on Kafka,
creates SponsorLead records in PostgreSQL, and publishes events
to Redis Stream for real-time dashboard updates.

This consumer replaces the synchronous HTTP call from real-time-service,
eliminating the 5-second timeout bottleneck.
"""
import json
import sys
import os
import logging
from datetime import datetime, timezone

# Add the app directory to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from kafka import KafkaConsumer
from app.core.config import settings
from app.db.session import SessionLocal
from app.crud.crud_sponsor import sponsor_lead, sponsor
from app.schemas.sponsor import SponsorLeadCreate
from app.db.redis import get_redis_client

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# Kafka topic
TOPIC_LEAD_CAPTURE = "lead.capture.events.v1"

# Redis Stream for real-time notifications
REDIS_STREAM_LEADS = "platform.leads.events.v1"


def get_db_session():
    """Get a database session."""
    return SessionLocal()


def publish_to_redis_stream(event_type: str, sponsor_id: str, lead_data: dict, booth_id: str = None):
    """
    Publish lead event to Redis Stream for real-time dashboard updates.

    The LeadEventsConsumer in real-time-service will consume these events
    and broadcast them to connected WebSocket clients.
    """
    try:
        redis_client = get_redis_client()

        payload = {
            "type": event_type,
            "sponsorId": sponsor_id,
            "eventId": lead_data.get("event_id"),
            "leadId": lead_data.get("id"),
            "boothId": booth_id,
            "data": {
                "id": lead_data.get("id"),
                "user_id": lead_data.get("user_id"),
                "user_name": lead_data.get("user_name"),
                "user_email": lead_data.get("user_email"),
                "user_company": lead_data.get("user_company"),
                "user_title": lead_data.get("user_title"),
                "intent_score": lead_data.get("intent_score"),
                "intent_level": lead_data.get("intent_level"),
                "interaction_type": lead_data.get("interaction_type"),
                "interaction_count": lead_data.get("interaction_count", 1),
                "first_interaction_at": lead_data.get("first_interaction_at"),
                "last_interaction_at": lead_data.get("last_interaction_at"),
                "created_at": lead_data.get("created_at"),
            },
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        # XADD adds to Redis Stream with auto-generated ID
        redis_client.xadd(REDIS_STREAM_LEADS, {"data": json.dumps(payload)})
        logger.info(f"Published {event_type} to Redis Stream for sponsor {sponsor_id}")
        return True

    except Exception as e:
        logger.error(f"Failed to publish to Redis Stream: {e}")
        return False


def process_lead_interaction_event(event_data: dict) -> bool:
    """
    Process a lead interaction event for intent score updates.

    This handles ongoing engagement (resource downloads, CTA clicks, video views)
    for existing leads, updating their intent scores accordingly.

    Args:
        event_data: Kafka message payload

    Returns:
        True if processed successfully, False otherwise
    """
    sponsor_id = event_data.get("sponsorId")
    event_id = event_data.get("eventId")
    user_id = event_data.get("userId")
    booth_id = event_data.get("boothId")
    interaction_type = event_data.get("interactionType")
    interaction_metadata = event_data.get("interactionMetadata", {})

    if not all([sponsor_id, event_id, user_id, interaction_type]):
        logger.error(f"Missing required fields in lead interaction event: {event_data}")
        return False

    logger.info(f"Processing lead interaction: {interaction_type} for sponsor {sponsor_id}, user {user_id}")

    try:
        db = get_db_session()

        try:
            # Check if this user is already a lead for this sponsor
            existing_lead = sponsor_lead.get_by_user_and_sponsor(
                db, user_id=user_id, sponsor_id=sponsor_id
            )

            if not existing_lead:
                # User is not a lead yet - just log and skip
                # (They need to fill out a form first to become a lead)
                logger.debug(f"User {user_id} is not a lead for sponsor {sponsor_id}, skipping intent update")
                return True

            old_intent_level = existing_lead.intent_level
            old_intent_score = existing_lead.intent_score

            # Create interaction update
            lead_in = SponsorLeadCreate(
                user_id=user_id,
                interaction_type=interaction_type,
                interaction_metadata={
                    **interaction_metadata,
                    "booth_id": booth_id,
                    "source": "kafka_interaction",
                }
            )

            # Update the lead (this adds interaction and recalculates score)
            lead = sponsor_lead.capture_lead(
                db,
                lead_in=lead_in,
                sponsor_id=sponsor_id,
                event_id=event_id,
            )

            # Check if intent changed
            intent_changed = (
                lead.intent_score != old_intent_score or
                lead.intent_level != old_intent_level
            )

            if intent_changed:
                logger.info(
                    f"Lead intent updated: {lead.id} - {old_intent_level}({old_intent_score}) -> {lead.intent_level}({lead.intent_score})"
                )

                # Convert to dict for Redis Stream
                lead_data = {
                    "id": lead.id,
                    "event_id": event_id,
                    "user_id": lead.user_id,
                    "user_name": lead.user_name,
                    "user_email": lead.user_email,
                    "user_company": lead.user_company,
                    "user_title": lead.user_title,
                    "intent_score": lead.intent_score,
                    "intent_level": lead.intent_level,
                    "interaction_type": interaction_type,
                    "interaction_count": lead.interaction_count,
                    "first_interaction_at": lead.first_interaction_at.isoformat() if lead.first_interaction_at else None,
                    "last_interaction_at": lead.last_interaction_at.isoformat() if lead.last_interaction_at else None,
                    "created_at": lead.created_at.isoformat() if lead.created_at else None,
                }

                # Publish LEAD_INTENT_UPDATED event to Redis Stream
                publish_to_redis_stream("LEAD_INTENT_UPDATED", sponsor_id, lead_data, booth_id)

                # Send email notification if lead upgraded to hot
                if lead.intent_level == "hot" and old_intent_level != "hot":
                    send_hot_lead_notification(db, sponsor_id, lead, event_id)
            else:
                logger.debug(f"Lead {lead.id} intent unchanged, no broadcast needed")

            return True

        finally:
            db.close()

    except Exception as e:
        logger.error(f"Failed to process lead interaction event: {e}", exc_info=True)
        return False


def process_lead_capture_event(event_data: dict) -> bool:
    """
    Process a lead capture event from real-time-service.

    Steps:
    1. Validate the event payload
    2. Check if lead already exists (to determine new vs update)
    3. Create/update SponsorLead record in PostgreSQL
    4. Publish appropriate event to Redis Stream:
       - LEAD_CAPTURED for new leads
       - LEAD_INTENT_UPDATED for existing leads with score changes
    5. Optionally send email notification

    Args:
        event_data: Kafka message payload

    Returns:
        True if processed successfully, False otherwise
    """
    event_type = event_data.get("type")

    if event_type != "LEAD_CAPTURED":
        logger.debug(f"Ignoring event type: {event_type}")
        return True  # Not an error, just not relevant

    sponsor_id = event_data.get("sponsorId")
    event_id = event_data.get("eventId")
    user_id = event_data.get("userId")
    booth_id = event_data.get("boothId")
    form_data = event_data.get("formData", {})

    if not all([sponsor_id, event_id, user_id]):
        logger.error(f"Missing required fields in lead capture event: {event_data}")
        return False

    logger.info(f"Processing lead capture for sponsor {sponsor_id}, user {user_id}")

    try:
        db = get_db_session()

        try:
            # Check if lead already exists BEFORE calling capture_lead
            # This allows us to determine if it's a new lead or an intent update
            existing_lead = sponsor_lead.get_by_user_and_sponsor(
                db, user_id=user_id, sponsor_id=sponsor_id
            )
            is_new_lead = existing_lead is None
            old_intent_level = existing_lead.intent_level if existing_lead else None
            old_intent_score = existing_lead.intent_score if existing_lead else 0

            # Create SponsorLeadCreate schema
            lead_in = SponsorLeadCreate(
                user_id=user_id,
                user_name=form_data.get("name"),
                user_email=form_data.get("email"),
                user_company=form_data.get("company"),
                user_title=form_data.get("jobTitle"),
                interaction_type="booth_contact_form",
                interaction_metadata={
                    "message": form_data.get("message"),
                    "phone": form_data.get("phone"),
                    "interests": form_data.get("interests"),
                    "marketing_consent": form_data.get("marketingConsent", False),
                    "booth_id": booth_id,
                    "source": "kafka_consumer",
                }
            )

            # Capture the lead (creates or updates)
            lead = sponsor_lead.capture_lead(
                db,
                lead_in=lead_in,
                sponsor_id=sponsor_id,
                event_id=event_id,
            )

            logger.info(f"Lead {'created' if is_new_lead else 'updated'}: {lead.id} (intent: {lead.intent_level}, score: {lead.intent_score})")

            # Convert to dict for Redis Stream
            lead_data = {
                "id": lead.id,
                "event_id": event_id,
                "user_id": lead.user_id,
                "user_name": lead.user_name,
                "user_email": lead.user_email,
                "user_company": lead.user_company,
                "user_title": lead.user_title,
                "intent_score": lead.intent_score,
                "intent_level": lead.intent_level,
                "interaction_type": "booth_contact_form",
                "interaction_count": lead.interaction_count,
                "first_interaction_at": lead.first_interaction_at.isoformat() if lead.first_interaction_at else None,
                "last_interaction_at": lead.last_interaction_at.isoformat() if lead.last_interaction_at else None,
                "created_at": lead.created_at.isoformat() if lead.created_at else None,
            }

            # Publish appropriate event type to Redis Stream
            if is_new_lead:
                # New lead - broadcast as LEAD_CAPTURED
                publish_to_redis_stream("LEAD_CAPTURED", sponsor_id, lead_data, booth_id)
            else:
                # Existing lead - broadcast as LEAD_INTENT_UPDATED
                # This triggers the handleIntentUpdated handler on the frontend
                publish_to_redis_stream("LEAD_INTENT_UPDATED", sponsor_id, lead_data, booth_id)
                logger.info(f"Intent changed for lead {lead.id}: {old_intent_level}({old_intent_score}) -> {lead.intent_level}({lead.intent_score})")

            # Optional: Send email notification for hot leads (only for new hot leads or upgrades to hot)
            if lead.intent_level == "hot" and (is_new_lead or old_intent_level != "hot"):
                send_hot_lead_notification(db, sponsor_id, lead, event_id)

            return True

        finally:
            db.close()

    except Exception as e:
        logger.error(f"Failed to process lead capture event: {e}", exc_info=True)
        return False


def send_hot_lead_notification(db, sponsor_id: str, lead, event_id: str):
    """Send email notification for hot leads."""
    try:
        from app.utils.sponsor_notifications import send_lead_notification_email

        # Get sponsor details for email
        sponsor_obj = sponsor.get(db, id=sponsor_id)
        if not sponsor_obj or not sponsor_obj.notification_email:
            return

        # Get event name (simplified - you might want to fetch from events table)
        event_name = "Event"

        send_lead_notification_email(
            notification_email=sponsor_obj.notification_email,
            sponsor_name=sponsor_obj.company_name,
            lead_name=lead.user_name or "Anonymous",
            lead_company=lead.user_company,
            lead_title=lead.user_title,
            intent_level=lead.intent_level,
            interaction_type="booth_contact_form",
            event_name=event_name,
        )
        logger.info(f"Sent hot lead notification to {sponsor_obj.notification_email}")

    except Exception as e:
        logger.error(f"Failed to send hot lead notification: {e}")


def get_kafka_consumer_config():
    """
    Build Kafka consumer configuration with SASL_SSL support for Confluent Cloud.
    """
    config = {
        "bootstrap_servers": settings.KAFKA_BOOTSTRAP_SERVERS,
        "value_deserializer": lambda v: json.loads(v.decode("utf-8")),
        "auto_offset_reset": "earliest",
        "enable_auto_commit": True,
        "auto_commit_interval_ms": 5000,
        "max_poll_records": 10,  # Process in small batches
    }

    # Add SASL authentication if credentials are provided (for Confluent Cloud)
    if settings.KAFKA_API_KEY and settings.KAFKA_API_SECRET:
        config.update({
            "security_protocol": settings.KAFKA_SECURITY_PROTOCOL or "SASL_SSL",
            "sasl_mechanism": settings.KAFKA_SASL_MECHANISM or "PLAIN",
            "sasl_plain_username": settings.KAFKA_API_KEY,
            "sasl_plain_password": settings.KAFKA_API_SECRET,
        })
        logger.info("Kafka configured with SASL_SSL authentication")

    return config


def run_consumer():
    """
    Main consumer loop for lead capture events.
    """
    kafka_auth = "SASL_SSL" if (settings.KAFKA_API_KEY and settings.KAFKA_API_SECRET) else "NONE"

    print("=" * 60)
    print("Lead Capture Consumer Service Starting...")
    print(f"Kafka Bootstrap Servers: {settings.KAFKA_BOOTSTRAP_SERVERS}")
    print(f"Kafka Authentication: {kafka_auth}")
    print(f"Topic: {TOPIC_LEAD_CAPTURE}")
    print(f"Redis Stream: {REDIS_STREAM_LEADS}")
    print(f"Database URL: {settings.DATABASE_URL[:50]}...")
    print("=" * 60)

    config = get_kafka_consumer_config()
    config["group_id"] = "lead-capture-consumer-group"

    try:
        consumer = KafkaConsumer(
            TOPIC_LEAD_CAPTURE,
            **config,
        )

        logger.info(f"Listening for messages on topic: {TOPIC_LEAD_CAPTURE}")

        for message in consumer:
            try:
                event_data = message.value
                event_type = event_data.get("type", "unknown")
                sponsor_id = event_data.get("sponsorId", "unknown")

                logger.info(f"Received lead event: {event_type} for sponsor {sponsor_id}")

                # Route to appropriate handler based on event type
                if event_type == "LEAD_CAPTURED":
                    success = process_lead_capture_event(event_data)
                elif event_type == "LEAD_INTERACTION":
                    success = process_lead_interaction_event(event_data)
                else:
                    logger.debug(f"Ignoring unknown event type: {event_type}")
                    success = True

                if not success:
                    logger.error(f"Failed to process {event_type} event for sponsor {sponsor_id}")
                    # Message will still be committed due to enable_auto_commit
                    # In production, you might want to implement a dead letter queue

            except Exception as e:
                logger.error(f"Error processing message: {e}", exc_info=True)

    except KeyboardInterrupt:
        logger.info("Shutting down lead capture consumer...")
    except Exception as e:
        logger.error(f"Consumer error: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    run_consumer()
