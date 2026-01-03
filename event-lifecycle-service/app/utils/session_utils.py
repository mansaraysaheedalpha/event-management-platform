# app/utils/session_utils.py
"""
Session utility functions for capacity management and access control.
"""

from typing import Optional
from sqlalchemy.orm import Session
from fastapi import HTTPException, status
import logging

logger = logging.getLogger(__name__)


def check_session_capacity(
    db: Session,
    session_id: str
) -> dict:
    """
    Check if a session is at capacity.

    This function checks:
    1. If the session has a capacity limit defined
    2. Current number of registered/checked-in attendees
    3. Whether new registrations are allowed

    Args:
        db: Database session
        session_id: Session ID to check

    Returns:
        Dictionary with:
        - is_full: bool - Whether session is at capacity
        - current: int - Current number of attendees
        - capacity: Optional[int] - Maximum capacity (None if unlimited)
        - available: int - Available spots (0 if full)

    Implementation:
    - Uses a default capacity of 100 per session
    - Counts accepted waitlist offers as current attendees
    - Can be extended to use venue capacity or session-specific capacity field
    """
    from app.models.session import Session as SessionModel

    # Get session
    session = db.query(SessionModel).filter(SessionModel.id == session_id).first()
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found"
        )

    # Get capacity
    # Option 1: Default capacity (simple, works out of the box)
    capacity = 100  # Default session capacity

    # Option 2: Venue capacity (if you want to use venue limits)
    # if session.event and session.event.venue and hasattr(session.event.venue, 'capacity'):
    #     capacity = session.event.venue.capacity

    # Count current attendees
    current = count_session_attendees(db, session_id)

    # Calculate availability
    is_full = current >= capacity
    available = max(0, capacity - current)

    logger.info(
        f"Session {session_id} capacity check: {current}/{capacity} "
        f"({'FULL' if is_full else f'{available} spots available'})"
    )

    return {
        "is_full": is_full,
        "current": current,
        "capacity": capacity,
        "available": available
    }


def count_session_attendees(db: Session, session_id: str) -> int:
    """
    Count current number of attendees for a session.

    This counts users who have:
    - Accepted waitlist offers (status = 'ACCEPTED')
    - This represents users who have secured their spot in the session

    Args:
        db: Database session
        session_id: Session ID

    Returns:
        Number of current attendees

    Note: This implementation uses accepted waitlist entries as a proxy for
    session attendance. For production, you may want to:
    - Create a dedicated session_attendees table
    - Track real-time check-ins
    - Integrate with event registration system
    """
    from app.models.session_waitlist import SessionWaitlist

    # Count users who have accepted offers for this session
    accepted_count = db.query(SessionWaitlist).filter(
        SessionWaitlist.session_id == session_id,
        SessionWaitlist.status == 'ACCEPTED'
    ).count()

    logger.debug(f"Session {session_id} has {accepted_count} accepted attendees")

    return accepted_count


def check_user_event_registration(
    db: Session,
    user_id: str,
    event_id: str
) -> bool:
    """
    Check if a user is registered for an event.

    Args:
        db: Database session
        user_id: User ID
        event_id: Event ID

    Returns:
        True if user is registered, False otherwise

    Raises:
        HTTPException: If event not found
    """
    from app.models.registration import Registration
    from app.models.event import Event

    # Verify event exists
    event = db.query(Event).filter(Event.id == event_id).first()
    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Event not found"
        )

    # Check if user has active registration
    registration = db.query(Registration).filter(
        Registration.event_id == event_id,
        Registration.user_id == user_id,
        Registration.status == 'confirmed'  # Only confirmed registrations
    ).first()

    return registration is not None


def get_user_registration(
    db: Session,
    user_id: str,
    event_id: str
) -> Optional[dict]:
    """
    Get user's registration details for an event.

    Args:
        db: Database session
        user_id: User ID
        event_id: Event ID

    Returns:
        Registration details dict or None if not registered
        Dictionary contains:
        - id: Registration ID
        - status: Registration status
        - ticket_code: Ticket code
        - checked_in_at: Check-in timestamp (if applicable)
    """
    from app.models.registration import Registration

    registration = db.query(Registration).filter(
        Registration.event_id == event_id,
        Registration.user_id == user_id
    ).first()

    if not registration:
        return None

    return {
        "id": registration.id,
        "status": registration.status,
        "ticket_code": registration.ticket_code,
        "checked_in_at": registration.checked_in_at
    }


def require_event_registration(
    db: Session,
    user_id: str,
    event_id: str
) -> None:
    """
    Require that a user is registered for an event, raise exception if not.

    Args:
        db: Database session
        user_id: User ID
        event_id: Event ID

    Raises:
        HTTPException: 403 if user not registered for event
    """
    if not check_user_event_registration(db, user_id, event_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You must be registered for this event to join the session waitlist"
        )
