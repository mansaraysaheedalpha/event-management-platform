#!/usr/bin/env python3
"""
Email Consumer Service

Listens for registration events on Kafka and sends confirmation emails via Resend.
"""
import json
import sys
import os

# Add the app directory to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from kafka import KafkaConsumer
from app.core.config import settings
from app.core.email import send_registration_confirmation

# Kafka topic for registration events
TOPIC_REGISTRATION_EVENTS = "registration.events.v1"


def process_registration_event(event_data: dict) -> None:
    """
    Process a registration event and send confirmation email.
    """
    event_type = event_data.get("type")

    if event_type != "REGISTRATION_CONFIRMED":
        print(f"[EMAIL CONSUMER] Ignoring event type: {event_type}")
        return

    recipient_email = event_data.get("recipientEmail")
    recipient_name = event_data.get("recipientName", "Attendee")
    event_name = event_data.get("eventName", "Event")
    event_start_date = event_data.get("eventStartDate", "TBD")
    ticket_code = event_data.get("ticketCode")
    venue_name = event_data.get("venueName")

    if not recipient_email:
        print(f"[EMAIL CONSUMER] No recipient email for registration: {event_data.get('registrationId')}")
        return

    if not settings.RESEND_API_KEY:
        print("[EMAIL CONSUMER] RESEND_API_KEY not configured. Skipping email.")
        return

    # Format the date nicely
    try:
        from datetime import datetime
        dt = datetime.fromisoformat(event_start_date.replace('Z', '+00:00'))
        formatted_date = dt.strftime("%B %d, %Y at %I:%M %p")
    except Exception:
        formatted_date = event_start_date

    print(f"[EMAIL CONSUMER] Sending confirmation to {recipient_email} for event: {event_name}")

    result = send_registration_confirmation(
        to_email=recipient_email,
        recipient_name=recipient_name,
        event_name=event_name,
        event_date=formatted_date,
        ticket_code=ticket_code,
        event_location=venue_name,
    )

    if result.get("success"):
        print(f"[EMAIL CONSUMER] Email sent successfully: {result.get('id')}")
    else:
        print(f"[EMAIL CONSUMER] Email failed: {result.get('error')}")


def run_consumer():
    """
    Main consumer loop - listens for registration events on Kafka.
    """
    print("=" * 60)
    print("Email Consumer Service Starting...")
    print(f"Kafka Bootstrap Servers: {settings.KAFKA_BOOTSTRAP_SERVERS}")
    print(f"Topic: {TOPIC_REGISTRATION_EVENTS}")
    print(f"Resend API Key: {'configured' if settings.RESEND_API_KEY else 'NOT CONFIGURED'}")
    print(f"From Domain: {settings.RESEND_FROM_DOMAIN}")
    print("=" * 60)

    consumer = KafkaConsumer(
        TOPIC_REGISTRATION_EVENTS,
        bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS,
        value_deserializer=lambda v: json.loads(v.decode("utf-8")),
        group_id="email-consumer-group",
        auto_offset_reset="earliest",
    )

    print(f"[EMAIL CONSUMER] Listening for messages on topic: {TOPIC_REGISTRATION_EVENTS}")

    for message in consumer:
        try:
            event_data = message.value
            print(f"[EMAIL CONSUMER] Received event: {event_data.get('type', 'unknown')}")
            process_registration_event(event_data)
        except Exception as e:
            print(f"[EMAIL CONSUMER ERROR] Failed to process message: {e}")


if __name__ == "__main__":
    run_consumer()
