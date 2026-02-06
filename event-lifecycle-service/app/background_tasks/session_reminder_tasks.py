"""
Background tasks for session reminder emails.

This module implements the session reminder scheduler that:
1. Checks for upcoming sessions every minute
2. Schedules reminder emails at configurable intervals (15 min, 5 min)
3. Sends reminder emails with magic link join buttons
4. Handles retries, failures, and delivery tracking
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import List, Optional

import httpx

from app.core.config import settings
from app.core.email import send_session_reminder_email
from app.crud.crud_session_reminder import session_reminder as crud_session_reminder
from app.db.session import SessionLocal
from app.models.session import Session
from app.models.registration import Registration
from app.schemas.session_reminder import SessionReminderCreate, ReminderType

logger = logging.getLogger(__name__)

# Configurable reminder intervals (minutes before session)
REMINDER_INTERVALS = [15, 5]

# Circuit breaker state for magic link service
_circuit_breaker = {
    "failures": 0,
    "last_failure": None,
    "threshold": 5,
    "reset_timeout": 60,  # seconds
}


def _circuit_breaker_open() -> bool:
    """Check if circuit breaker is open (should not call external service)."""
    if _circuit_breaker["failures"] < _circuit_breaker["threshold"]:
        return False

    if _circuit_breaker["last_failure"] is None:
        return False

    elapsed = (datetime.now(timezone.utc) - _circuit_breaker["last_failure"]).seconds
    if elapsed > _circuit_breaker["reset_timeout"]:
        # Reset circuit breaker
        _circuit_breaker["failures"] = 0
        _circuit_breaker["last_failure"] = None
        return False

    return True


def _record_circuit_failure():
    """Record a failure for circuit breaker."""
    _circuit_breaker["failures"] += 1
    _circuit_breaker["last_failure"] = datetime.now(timezone.utc)


def _record_circuit_success():
    """Record a success (reset failure count)."""
    _circuit_breaker["failures"] = 0


def generate_magic_link(
    user_id: str,
    session_id: str,
    event_id: str,
    registration_id: str,
    session_end: datetime,
) -> tuple[str, Optional[str]]:
    """
    Generate a magic link for direct session access.

    Calls the user-and-org-service to generate a magic link.
    Implements circuit breaker pattern for resilience.

    Returns:
        Tuple of (url, token_jti) where token_jti is the JWT ID for tracking
    """
    if _circuit_breaker_open():
        logger.warning("Circuit breaker open, using fallback URL")
        return _get_fallback_url(event_id, session_id), None

    try:
        with httpx.Client(timeout=5.0) as client:
            response = client.post(
                f"{settings.USER_SERVICE_URL}/auth/magic-link/generate",
                json={
                    "userId": user_id,
                    "sessionId": session_id,
                    "eventId": event_id,
                    "registrationId": registration_id,
                    "sessionEndTime": session_end.isoformat(),
                },
                headers={"x-internal-api-key": settings.INTERNAL_API_KEY},
            )

            if response.status_code == 200:
                data = response.json()
                _record_circuit_success()
                return data.get("url"), data.get("jti")
            else:
                logger.warning(
                    f"Magic link service returned {response.status_code}: {response.text}"
                )
                _record_circuit_failure()

    except httpx.TimeoutException:
        logger.warning("Magic link service timeout")
        _record_circuit_failure()
    except httpx.RequestError as e:
        logger.warning(f"Magic link service request error: {e}")
        _record_circuit_failure()
    except Exception as e:
        logger.error(f"Unexpected error calling magic link service: {e}")
        _record_circuit_failure()

    return _get_fallback_url(event_id, session_id), None


def _get_fallback_url(event_id: str, session_id: str) -> str:
    """Get fallback URL when magic link service is unavailable."""
    return f"{settings.FRONTEND_URL}/attendee/events/{event_id}?session={session_id}"


def fetch_user_info(user_id: str) -> dict | None:
    """
    Fetch user info (email, name) from user-and-org-service.

    Returns dict with email, firstName, lastName or None if not found.
    """
    if _circuit_breaker_open():
        return None

    try:
        with httpx.Client(timeout=5.0) as client:
            response = client.get(
                f"{settings.USER_SERVICE_URL}/internal/users/{user_id}",
                headers={"x-internal-api-key": settings.INTERNAL_API_KEY},
            )

            if response.status_code == 200:
                data = response.json()
                _record_circuit_success()
                return {
                    "email": data.get("email"),
                    "firstName": data.get("first_name") or data.get("firstName"),
                    "lastName": data.get("last_name") or data.get("lastName"),
                }
            else:
                logger.warning(f"User service returned {response.status_code} for user {user_id}")

    except httpx.TimeoutException:
        logger.warning(f"User service timeout fetching user {user_id}")
        _record_circuit_failure()
    except httpx.RequestError as e:
        logger.warning(f"User service request error: {e}")
        _record_circuit_failure()
    except Exception as e:
        logger.error(f"Unexpected error fetching user info: {e}")

    return None


def get_sessions_in_window(
    db,
    window_start: datetime,
    window_end: datetime,
) -> List[Session]:
    """
    Get all sessions starting within the given time window.
    Uses batch query for scalability.
    """
    from sqlalchemy.orm import joinedload

    return (
        db.query(Session)
        .filter(
            Session.start_time >= window_start,
            Session.start_time <= window_end,
            Session.is_archived == False,
        )
        .options(
            joinedload(Session.event),
            joinedload(Session.speakers),
        )
        .all()
    )


def get_event_attendees(db, event_id: str) -> List[Registration]:
    """
    Get all confirmed attendees for an event.
    Returns registrations with user info.
    """
    return (
        db.query(Registration)
        .filter(
            Registration.event_id == event_id,
            Registration.status.in_(["confirmed", "checked_in"]),
            Registration.is_archived == "false",
        )
        .all()
    )


def check_upcoming_sessions():
    """
    Main scheduler task: Check for upcoming sessions and schedule reminders.

    Runs every minute via APScheduler.
    Finds sessions starting within reminder windows and creates reminder records.
    """
    db = SessionLocal()
    now = datetime.now(timezone.utc)
    total_reminders_scheduled = 0

    try:
        logger.info("Checking for upcoming sessions...")

        for minutes in REMINDER_INTERVALS:
            # Find sessions starting in exactly `minutes` from now (±1 min window)
            window_start = now + timedelta(minutes=minutes - 1)
            window_end = now + timedelta(minutes=minutes + 1)

            sessions = get_sessions_in_window(db, window_start, window_end)
            logger.debug(
                f"Found {len(sessions)} sessions starting in ~{minutes} minutes"
            )

            for session in sessions:
                # Get all registered attendees for this session's event
                attendees = get_event_attendees(db, session.event_id)

                for attendee in attendees:
                    # Determine user info
                    user_id = attendee.user_id
                    user_email = attendee.guest_email or None
                    user_name = attendee.guest_name or "Attendee"

                    # Skip if no email available
                    if not user_email and not user_id:
                        continue

                    # Create reminder record (idempotent - will skip duplicates)
                    reminder_type = f"{minutes}_MIN"
                    reminder_create = SessionReminderCreate(
                        registration_id=attendee.id,
                        session_id=session.id,
                        user_id=user_id,
                        event_id=session.event_id,
                        reminder_type=ReminderType(reminder_type),
                        scheduled_at=now,
                    )

                    reminder = crud_session_reminder.create(db, obj_in=reminder_create)
                    if reminder:
                        total_reminders_scheduled += 1

        if total_reminders_scheduled > 0:
            logger.info(f"Scheduled {total_reminders_scheduled} new reminders")

    except Exception as e:
        logger.error(f"Error in check_upcoming_sessions: {e}")
        db.rollback()
    finally:
        db.close()


def send_pending_reminders():
    """
    Process and send pending reminder emails.

    Runs every minute via APScheduler.
    Picks up queued reminders and sends them with magic links.
    """
    db = SessionLocal()
    sent_count = 0
    failed_count = 0

    try:
        # Get batch of pending reminders
        pending = crud_session_reminder.get_pending_reminders(db, batch_size=50)

        if not pending:
            return

        logger.info(f"Processing {len(pending)} pending reminders")

        for reminder in pending:
            try:
                # Extract reminder minutes from type
                minutes = int(reminder.reminder_type.replace("_MIN", ""))

                # Get session and registration details
                session = reminder.session
                registration = reminder.registration

                if not session or not registration:
                    logger.warning(
                        f"Missing session/registration for reminder {reminder.id}"
                    )
                    crud_session_reminder.mark_as_failed(
                        db,
                        reminder_id=reminder.id,
                        error_message="Missing session or registration data",
                    )
                    failed_count += 1
                    continue

                # Determine attendee info
                user_email = registration.guest_email
                user_name = registration.guest_name or "Attendee"
                user_id = registration.user_id

                # If no guest_email but we have user_id, fetch from user service
                if not user_email and user_id:
                    user_info = fetch_user_info(user_id)
                    if user_info and user_info.get("email"):
                        user_email = user_info["email"]
                        first_name = user_info.get("firstName", "")
                        last_name = user_info.get("lastName", "")
                        user_name = f"{first_name} {last_name}".strip() or "Attendee"
                        logger.debug(f"Fetched user info for {user_id}: {user_email}")

                # Skip if still no email available
                if not user_email:
                    logger.warning(
                        f"No email available for reminder {reminder.id}, skipping"
                    )
                    crud_session_reminder.mark_as_failed(
                        db,
                        reminder_id=reminder.id,
                        error_message="No email address available",
                    )
                    failed_count += 1
                    continue

                # Generate magic link
                join_url, token_jti = generate_magic_link(
                    user_id=user_id or registration.id,
                    session_id=session.id,
                    event_id=session.event_id,
                    registration_id=registration.id,
                    session_end=session.end_time,
                )

                # Get speaker names
                speaker_names = []
                if hasattr(session, "speakers") and session.speakers:
                    speaker_names = [s.name for s in session.speakers if s.name]

                # Format session start time
                session_start_formatted = session.start_time.strftime(
                    "%B %d, %Y at %I:%M %p %Z"
                )

                # Get event name
                event_name = session.event.name if session.event else "Event"

                # Send the email
                result = send_session_reminder_email(
                    to_email=user_email,
                    attendee_name=user_name,
                    session_title=session.title,
                    session_start_time=session_start_formatted,
                    event_name=event_name,
                    speaker_names=speaker_names,
                    join_url=join_url,
                    minutes_until_start=minutes,
                )

                if result.get("success"):
                    crud_session_reminder.mark_as_sent(
                        db,
                        reminder_id=reminder.id,
                        magic_link_token_jti=token_jti,
                    )
                    sent_count += 1
                    logger.debug(
                        f"Sent {minutes}min reminder to {user_email} for session {session.title}"
                    )
                else:
                    error_msg = result.get("error", "Unknown email error")
                    crud_session_reminder.mark_as_failed(
                        db,
                        reminder_id=reminder.id,
                        error_message=error_msg,
                    )
                    failed_count += 1
                    logger.warning(
                        f"Failed to send reminder {reminder.id}: {error_msg}"
                    )

            except Exception as e:
                logger.error(f"Error processing reminder {reminder.id}: {e}")
                crud_session_reminder.mark_as_failed(
                    db,
                    reminder_id=reminder.id,
                    error_message=str(e),
                )
                failed_count += 1

        if sent_count > 0 or failed_count > 0:
            logger.info(
                f"Reminder batch complete: {sent_count} sent, {failed_count} failed"
            )

    except Exception as e:
        logger.error(f"Error in send_pending_reminders: {e}")
        db.rollback()
    finally:
        db.close()


def retry_failed_reminders():
    """
    Retry sending failed reminders (dead letter processing).

    Runs every 5 minutes via APScheduler.
    Attempts to resend failed reminders with exponential backoff tracking.
    """
    db = SessionLocal()

    try:
        failed = crud_session_reminder.get_failed_reminders(db, limit=20)

        if not failed:
            return

        logger.info(f"Retrying {len(failed)} failed reminders")

        for reminder in failed:
            # Check if session hasn't started yet (no point sending after)
            session = reminder.session
            if session and session.start_time:
                # Ensure timezone-aware comparison
                start_time = session.start_time
                if start_time.tzinfo is None:
                    start_time = start_time.replace(tzinfo=timezone.utc)
                if start_time < datetime.now(timezone.utc):
                    logger.debug(
                        f"Skipping retry for reminder {reminder.id} - session already started"
                    )
                    continue

            # Reset status to QUEUED for retry
            reminder.email_status = "QUEUED"
            reminder.error_message = None
            db.add(reminder)

        db.commit()
        logger.info(f"Queued {len(failed)} reminders for retry")

    except Exception as e:
        logger.error(f"Error in retry_failed_reminders: {e}")
        db.rollback()
    finally:
        db.close()


def get_reminder_metrics() -> dict:
    """
    Get reminder system metrics for monitoring.

    Returns:
        Dict with counts by status and recent failure rate
    """
    db = SessionLocal()

    try:
        stats = crud_session_reminder.get_reminder_stats(db)

        total = sum(stats.values())
        failed_rate = stats.get("FAILED", 0) / total if total > 0 else 0

        return {
            "total_reminders": total,
            "by_status": stats,
            "failure_rate": round(failed_rate * 100, 2),
            "circuit_breaker_failures": _circuit_breaker["failures"],
            "circuit_breaker_open": _circuit_breaker_open(),
        }

    except Exception as e:
        logger.error(f"Error getting reminder metrics: {e}")
        return {"error": str(e)}
    finally:
        db.close()
