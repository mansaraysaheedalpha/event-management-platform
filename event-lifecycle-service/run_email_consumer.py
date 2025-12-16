#!/usr/bin/env python3
"""
Email Consumer Service

Listens for registration and giveaway events on Kafka and sends emails via Resend.
"""
import json
import sys
import os
import threading

# Add the app directory to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from kafka import KafkaConsumer
from app.core.config import settings
from app.core.email import send_registration_confirmation, send_giveaway_winner_email

# Kafka topics
TOPIC_REGISTRATION_EVENTS = "registration.events.v1"
TOPIC_GIVEAWAY_EVENTS = "giveaway.events.v1"


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


def process_giveaway_event(event_data: dict) -> None:
    """
    Process a giveaway event and send winner notification email.
    """
    event_type = event_data.get("type")

    if event_type not in ["GIVEAWAY_WINNER_SINGLE_POLL", "GIVEAWAY_WINNER_QUIZ"]:
        print(f"[EMAIL CONSUMER] Ignoring giveaway event type: {event_type}")
        return

    winner_email = event_data.get("winnerEmail")
    winner_name = event_data.get("winnerName", "Winner")
    event_name = event_data.get("eventName", "Event")
    session_name = event_data.get("sessionName")
    giveaway_type = "QUIZ_SCORE" if event_type == "GIVEAWAY_WINNER_QUIZ" else "SINGLE_POLL"

    # Prize details
    prize_title = event_data.get("prizeTitle")
    prize_description = event_data.get("prizeDescription")
    claim_instructions = event_data.get("claimInstructions")
    claim_location = event_data.get("claimLocation")
    claim_deadline = event_data.get("claimDeadline")

    # Quiz-specific details
    quiz_score = event_data.get("quizScore")
    quiz_total = event_data.get("quizTotal")

    # Poll-specific details
    winning_option_text = event_data.get("winningOptionText")

    if not winner_email:
        print(f"[EMAIL CONSUMER] No winner email for giveaway: {event_data.get('giveawayWinnerId')}")
        return

    if not settings.RESEND_API_KEY:
        print("[EMAIL CONSUMER] RESEND_API_KEY not configured. Skipping email.")
        return

    # Format the deadline nicely
    formatted_deadline = None
    if claim_deadline:
        try:
            from datetime import datetime
            dt = datetime.fromisoformat(claim_deadline.replace('Z', '+00:00'))
            formatted_deadline = dt.strftime("%B %d, %Y at %I:%M %p")
        except Exception:
            formatted_deadline = claim_deadline

    print(f"[EMAIL CONSUMER] Sending giveaway winner notification to {winner_email} for event: {event_name}")

    result = send_giveaway_winner_email(
        to_email=winner_email,
        winner_name=winner_name,
        event_name=event_name,
        session_name=session_name,
        giveaway_type=giveaway_type,
        prize_title=prize_title,
        prize_description=prize_description,
        claim_instructions=claim_instructions,
        claim_location=claim_location,
        claim_deadline=formatted_deadline,
        quiz_score=quiz_score,
        quiz_total=quiz_total,
        winning_option_text=winning_option_text,
    )

    if result.get("success"):
        print(f"[EMAIL CONSUMER] Giveaway email sent successfully: {result.get('id')}")
    else:
        print(f"[EMAIL CONSUMER] Giveaway email failed: {result.get('error')}")


def run_registration_consumer():
    """
    Consumer loop for registration events.
    """
    consumer = KafkaConsumer(
        TOPIC_REGISTRATION_EVENTS,
        bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS,
        value_deserializer=lambda v: json.loads(v.decode("utf-8")),
        group_id="email-consumer-registration-group",
        auto_offset_reset="earliest",
    )

    print(f"[EMAIL CONSUMER] Listening for messages on topic: {TOPIC_REGISTRATION_EVENTS}")

    for message in consumer:
        try:
            event_data = message.value
            print(f"[EMAIL CONSUMER] Received registration event: {event_data.get('type', 'unknown')}")
            process_registration_event(event_data)
        except Exception as e:
            print(f"[EMAIL CONSUMER ERROR] Failed to process registration message: {e}")


def run_giveaway_consumer():
    """
    Consumer loop for giveaway events.
    """
    consumer = KafkaConsumer(
        TOPIC_GIVEAWAY_EVENTS,
        bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS,
        value_deserializer=lambda v: json.loads(v.decode("utf-8")),
        group_id="email-consumer-giveaway-group",
        auto_offset_reset="earliest",
    )

    print(f"[EMAIL CONSUMER] Listening for messages on topic: {TOPIC_GIVEAWAY_EVENTS}")

    for message in consumer:
        try:
            event_data = message.value
            print(f"[EMAIL CONSUMER] Received giveaway event: {event_data.get('type', 'unknown')}")
            process_giveaway_event(event_data)
        except Exception as e:
            print(f"[EMAIL CONSUMER ERROR] Failed to process giveaway message: {e}")


def run_consumer():
    """
    Main consumer - runs both registration and giveaway consumers in parallel threads.
    """
    print("=" * 60)
    print("Email Consumer Service Starting...")
    print(f"Kafka Bootstrap Servers: {settings.KAFKA_BOOTSTRAP_SERVERS}")
    print(f"Topics: {TOPIC_REGISTRATION_EVENTS}, {TOPIC_GIVEAWAY_EVENTS}")
    print(f"Resend API Key: {'configured' if settings.RESEND_API_KEY else 'NOT CONFIGURED'}")
    print(f"From Domain: {settings.RESEND_FROM_DOMAIN}")
    print("=" * 60)

    # Start registration consumer thread
    registration_thread = threading.Thread(target=run_registration_consumer, daemon=True)
    registration_thread.start()

    # Start giveaway consumer thread
    giveaway_thread = threading.Thread(target=run_giveaway_consumer, daemon=True)
    giveaway_thread.start()

    # Keep main thread alive
    try:
        registration_thread.join()
        giveaway_thread.join()
    except KeyboardInterrupt:
        print("\n[EMAIL CONSUMER] Shutting down...")


if __name__ == "__main__":
    run_consumer()
