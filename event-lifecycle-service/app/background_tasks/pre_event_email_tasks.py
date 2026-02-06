"""
Background tasks for pre-event engagement emails.

This module implements the pre-event email system that:
1. Checks daily at 9 AM UTC for events starting tomorrow
2. Queues personalized agenda and networking emails for attendees
3. Sends emails in batches with rate limiting
4. Handles retries for failed emails

Email types:
- AGENDA: Personalized session recommendations and expo booths
- NETWORKING: People-to-meet recommendations with conversation starters
"""

import logging
from datetime import datetime, timedelta, timezone, date
from typing import List, Optional

from app.core.config import settings
from app.core.email import send_pre_event_agenda_email, send_people_to_meet_email
from app.crud.crud_email_preference import email_preference as crud_email_preference
from app.crud.crud_pre_event_email import pre_event_email as crud_pre_event_email
from app.db.session import SessionLocal
from app.models.event import Event
from app.models.registration import Registration
from app.models.session import Session
from app.schemas.pre_event_email import PreEventEmailCreate, PreEventEmailType
from app.services.realtime_client import realtime_client

logger = logging.getLogger(__name__)

# Batch size for processing attendees
BATCH_SIZE = 100


def check_events_starting_tomorrow():
    """
    Main scheduler task: Find events starting tomorrow and queue emails.

    Runs daily at 9 AM UTC via APScheduler.
    Finds all published events starting in the next 24-48 hours and
    creates email records for registered attendees.
    """
    db = SessionLocal()
    total_emails_queued = 0

    try:
        now = datetime.now(timezone.utc)
        # Find events starting tomorrow (24-48 hours from now)
        tomorrow_start = (now + timedelta(days=1)).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        tomorrow_end = tomorrow_start + timedelta(days=1)

        logger.info(
            f"Checking for events starting between {tomorrow_start} and {tomorrow_end}"
        )

        # Find published events starting tomorrow
        events = (
            db.query(Event)
            .filter(
                Event.start_date >= tomorrow_start,
                Event.start_date < tomorrow_end,
                Event.status == "published",
                Event.is_archived == False,
            )
            .all()
        )

        logger.info(f"Found {len(events)} events starting tomorrow")

        for event in events:
            emails_for_event = _queue_emails_for_event(db, event)
            total_emails_queued += emails_for_event
            logger.info(f"Queued {emails_for_event} emails for event {event.name}")

        if total_emails_queued > 0:
            logger.info(f"Total emails queued: {total_emails_queued}")

    except Exception as e:
        logger.error(f"Error in check_events_starting_tomorrow: {e}")
        db.rollback()
    finally:
        db.close()


def _queue_emails_for_event(db, event: Event) -> int:
    """
    Queue pre-event emails for all attendees of an event.

    Args:
        db: Database session
        event: The event to queue emails for

    Returns:
        Number of emails queued
    """
    emails_queued = 0
    email_date = date.today()
    now = datetime.now(timezone.utc)

    # Get all confirmed attendees for this event
    attendees = (
        db.query(Registration)
        .filter(
            Registration.event_id == event.id,
            Registration.status.in_(["confirmed", "checked_in"]),
            Registration.is_archived == "false",
        )
        .all()
    )

    logger.debug(f"Found {len(attendees)} attendees for event {event.id}")

    for attendee in attendees:
        user_id = attendee.user_id or attendee.id  # Use registration ID if no user_id

        # Check email preferences for agenda email
        if crud_email_preference.should_send_pre_event_agenda(
            db, user_id=user_id, event_id=event.id
        ):
            # Create AGENDA email record
            email_record = crud_pre_event_email.create(
                db,
                obj_in=PreEventEmailCreate(
                    registration_id=attendee.id,
                    event_id=event.id,
                    user_id=attendee.user_id,
                    email_type=PreEventEmailType.AGENDA,
                    email_date=email_date,
                    scheduled_at=now,
                ),
            )
            if email_record:
                emails_queued += 1

        # Check email preferences for networking email (only for registered users)
        if attendee.user_id and crud_email_preference.should_send_pre_event_networking(
            db, user_id=attendee.user_id, event_id=event.id
        ):
            # Create NETWORKING email record
            email_record = crud_pre_event_email.create(
                db,
                obj_in=PreEventEmailCreate(
                    registration_id=attendee.id,
                    event_id=event.id,
                    user_id=attendee.user_id,
                    email_type=PreEventEmailType.NETWORKING,
                    email_date=email_date,
                    scheduled_at=now,
                ),
            )
            if email_record:
                emails_queued += 1

    return emails_queued


def send_pending_pre_event_emails():
    """
    Process and send pending pre-event emails.

    Runs every 2 minutes via APScheduler.
    Picks up QUEUED emails and sends them via Resend.
    """
    db = SessionLocal()
    sent_count = 0
    failed_count = 0

    try:
        # Get batch of pending emails
        pending = crud_pre_event_email.get_pending_emails(db, batch_size=BATCH_SIZE)

        if not pending:
            return

        logger.info(f"Processing {len(pending)} pending pre-event emails")

        for email_record in pending:
            try:
                result = _send_single_email(db, email_record)
                if result:
                    sent_count += 1
                else:
                    failed_count += 1
            except Exception as e:
                logger.error(f"Error processing email {email_record.id}: {e}")
                crud_pre_event_email.mark_as_failed(
                    db, email_id=email_record.id, error_message=str(e)
                )
                failed_count += 1

        if sent_count > 0 or failed_count > 0:
            logger.info(
                f"Pre-event email batch complete: {sent_count} sent, {failed_count} failed"
            )

    except Exception as e:
        logger.error(f"Error in send_pending_pre_event_emails: {e}")
        db.rollback()
    finally:
        db.close()


def _send_single_email(db, email_record) -> bool:
    """
    Send a single pre-event email.

    Args:
        db: Database session
        email_record: PreEventEmail record to send

    Returns:
        True if sent successfully, False otherwise
    """
    registration = email_record.registration
    event = email_record.event

    if not registration or not event:
        logger.warning(f"Missing registration/event for email {email_record.id}")
        crud_pre_event_email.mark_as_failed(
            db, email_id=email_record.id, error_message="Missing registration or event"
        )
        return False

    # Determine attendee info
    user_email = registration.guest_email
    user_name = registration.guest_name or "Attendee"
    user_id = registration.user_id

    # If we have user_id but no email, skip (would need user service call)
    if not user_email and user_id:
        logger.debug(f"No email available for user {user_id}, skipping")
        crud_pre_event_email.mark_as_failed(
            db, email_id=email_record.id, error_message="No email address available"
        )
        return False

    if not user_email:
        crud_pre_event_email.mark_as_failed(
            db, email_id=email_record.id, error_message="No email address"
        )
        return False

    # Format event URL
    event_url = f"{settings.FRONTEND_URL}/attendee/events/{event.id}"

    # Send based on email type
    if email_record.email_type == "AGENDA":
        result = _send_agenda_email(
            db, email_record, user_email, user_name, event, event_url
        )
    elif email_record.email_type == "NETWORKING":
        result = _send_networking_email(
            db, email_record, user_email, user_name, user_id, event, event_url
        )
    else:
        crud_pre_event_email.mark_as_failed(
            db,
            email_id=email_record.id,
            error_message=f"Unknown email type: {email_record.email_type}",
        )
        return False

    return result


def _send_agenda_email(
    db,
    email_record,
    user_email: str,
    user_name: str,
    event: Event,
    event_url: str,
) -> bool:
    """Send personalized agenda email."""
    # Get sessions for this event
    sessions = (
        db.query(Session)
        .filter(
            Session.event_id == event.id,
            Session.is_archived == False,
        )
        .order_by(Session.start_time)
        .limit(10)
        .all()
    )

    # Format session data
    sessions_data = [
        {
            "session_id": s.id,
            "title": s.title,
            "start_time": s.start_time.strftime("%I:%M %p") if s.start_time else "",
            "end_time": s.end_time.strftime("%I:%M %p") if s.end_time else "",
            "speakers": [sp.name for sp in s.speakers] if hasattr(s, "speakers") and s.speakers else [],
        }
        for s in sessions[:5]
    ]

    # Get booths (if expo exists)
    booths_data = []
    # Note: Booth fetching would go here if expo tables are available

    # Send the email
    result = send_pre_event_agenda_email(
        to_email=user_email,
        attendee_name=user_name,
        event_name=event.name,
        event_date=event.start_date.strftime("%B %d, %Y"),
        event_url=event_url,
        sessions=sessions_data,
        booths=booths_data,
        event_location=None,
    )

    if result.get("success"):
        crud_pre_event_email.mark_as_sent(
            db, email_id=email_record.id, resend_message_id=result.get("id")
        )
        logger.debug(f"Sent agenda email to {user_email}")
        return True
    else:
        crud_pre_event_email.mark_as_failed(
            db, email_id=email_record.id, error_message=result.get("error", "Unknown")
        )
        logger.warning(f"Failed to send agenda email to {user_email}: {result.get('error')}")
        return False


def _send_networking_email(
    db,
    email_record,
    user_email: str,
    user_name: str,
    user_id: str,
    event: Event,
    event_url: str,
) -> bool:
    """Send people-to-meet networking email."""
    if not user_id:
        crud_pre_event_email.mark_as_failed(
            db, email_id=email_record.id, error_message="No user_id for networking"
        )
        return False

    # Get recommendations from real-time-service
    recommendations = realtime_client.get_recommendations_for_user(
        user_id=user_id, event_id=event.id, limit=5
    )

    if not recommendations:
        # No recommendations available - mark as failed but don't retry
        crud_pre_event_email.mark_as_failed(
            db,
            email_id=email_record.id,
            error_message="No recommendations available",
        )
        logger.debug(f"No recommendations for user {user_id}, skipping networking email")
        return False

    # Format people data
    people_data = []
    for r in recommendations:
        user_info = r.get("user", {})
        people_data.append({
            "user_id": r.get("recommendedUserId", r.get("userId", "")),
            "name": user_info.get("name", "Attendee"),
            "role": user_info.get("role", user_info.get("title", "")),
            "company": user_info.get("company", user_info.get("organization", "")),
            "avatar_url": user_info.get("avatarUrl", user_info.get("avatar", "")),
            "match_score": r.get("matchScore", r.get("score", 0)),
            "reasons": r.get("reasons", r.get("matchReasons", [])),
            "conversation_starters": r.get("conversationStarters", r.get("iceBreakers", [])),
        })

    # Send the email
    result = send_people_to_meet_email(
        to_email=user_email,
        attendee_name=user_name,
        event_name=event.name,
        event_date=event.start_date.strftime("%B %d, %Y"),
        event_url=f"{event_url}/networking",
        people=people_data,
    )

    if result.get("success"):
        crud_pre_event_email.mark_as_sent(
            db, email_id=email_record.id, resend_message_id=result.get("id")
        )
        logger.debug(f"Sent networking email to {user_email}")
        return True
    else:
        crud_pre_event_email.mark_as_failed(
            db, email_id=email_record.id, error_message=result.get("error", "Unknown")
        )
        logger.warning(f"Failed to send networking email to {user_email}: {result.get('error')}")
        return False


def retry_failed_pre_event_emails():
    """
    Retry sending failed pre-event emails.

    Runs every 10 minutes via APScheduler.
    Attempts to resend failed emails if the event hasn't started yet.
    """
    db = SessionLocal()
    retried_count = 0

    try:
        failed = crud_pre_event_email.get_failed_emails(db, limit=50)

        if not failed:
            return

        logger.info(f"Retrying {len(failed)} failed pre-event emails")

        now = datetime.now(timezone.utc)

        for email_record in failed:
            # Check if event hasn't started yet
            event = email_record.event
            if event and event.start_date and event.start_date < now:
                logger.debug(
                    f"Skipping retry for email {email_record.id} - event already started"
                )
                continue

            # Reset status to QUEUED for retry
            email_record.email_status = "QUEUED"
            email_record.error_message = None
            db.add(email_record)
            retried_count += 1

        if retried_count > 0:
            db.commit()
            logger.info(f"Queued {retried_count} emails for retry")

    except Exception as e:
        logger.error(f"Error in retry_failed_pre_event_emails: {e}")
        db.rollback()
    finally:
        db.close()


def get_pre_event_email_metrics() -> dict:
    """
    Get pre-event email metrics for monitoring.

    Returns:
        Dict with counts by status, email type, and circuit breaker status
    """
    db = SessionLocal()

    try:
        stats = crud_pre_event_email.get_email_stats(db)
        circuit_status = realtime_client.get_circuit_breaker_status()

        return {
            "email_stats": stats,
            "circuit_breaker": circuit_status,
        }

    except Exception as e:
        logger.error(f"Error getting pre-event email metrics: {e}")
        return {"error": str(e)}
    finally:
        db.close()
