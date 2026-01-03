# app/utils/validators.py
"""
Input validation utilities for security and data integrity.
"""

import re
from typing import Optional
from fastapi import HTTPException, status


def validate_session_id(session_id: str) -> str:
    """
    Validate session_id format to prevent injection attacks.

    Expected format: ses_[12 alphanumeric chars]
    Example: ses_abc123xyz789

    Args:
        session_id: Session ID to validate

    Returns:
        The validated session_id

    Raises:
        HTTPException: If format is invalid
    """
    if not session_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="session_id is required"
        )

    # Validate format: ses_[alphanumeric]
    if not re.match(r'^ses_[a-z0-9]{12}$', session_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid session_id format. Expected: ses_[12 alphanumeric chars]"
        )

    return session_id


def validate_event_id(event_id: str) -> str:
    """
    Validate event_id format to prevent injection attacks.

    Expected format: evt_[12 alphanumeric chars]

    Args:
        event_id: Event ID to validate

    Returns:
        The validated event_id

    Raises:
        HTTPException: If format is invalid
    """
    if not event_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="event_id is required"
        )

    if not re.match(r'^evt_[a-z0-9]{12}$', event_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid event_id format"
        )

    return event_id


def validate_user_id(user_id: str) -> str:
    """
    Validate user_id format to prevent injection attacks.

    Expected format: usr_[12 alphanumeric chars]

    Args:
        user_id: User ID to validate

    Returns:
        The validated user_id

    Raises:
        HTTPException: If format is invalid
    """
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="user_id is required"
        )

    if not re.match(r'^usr_[a-z0-9]{12}$', user_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid user_id format"
        )

    return user_id


def validate_priority_tier(priority_tier: str) -> str:
    """
    Validate priority tier value.

    Args:
        priority_tier: Priority tier to validate

    Returns:
        The validated priority_tier (uppercased)

    Raises:
        HTTPException: If tier is invalid
    """
    valid_tiers = {'VIP', 'PREMIUM', 'STANDARD'}
    tier_upper = priority_tier.upper()

    if tier_upper not in valid_tiers:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid priority_tier. Must be one of: {', '.join(valid_tiers)}"
        )

    return tier_upper


def validate_waitlist_status(status_value: str) -> str:
    """
    Validate waitlist status value.

    Args:
        status_value: Status to validate

    Returns:
        The validated status (uppercased)

    Raises:
        HTTPException: If status is invalid
    """
    valid_statuses = {'WAITING', 'OFFERED', 'ACCEPTED', 'DECLINED', 'EXPIRED', 'LEFT'}
    status_upper = status_value.upper()

    if status_upper not in valid_statuses:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid status. Must be one of: {', '.join(valid_statuses)}"
        )

    return status_upper


def validate_status_transition(current_status: str, new_status: str) -> bool:
    """
    Validate if status transition is allowed.

    Valid transitions:
    - WAITING → OFFERED, LEFT
    - OFFERED → ACCEPTED, DECLINED, EXPIRED, LEFT
    - ACCEPTED → (terminal state, no transitions)
    - DECLINED → (terminal state, no transitions)
    - EXPIRED → (terminal state, no transitions)
    - LEFT → (terminal state, no transitions)

    Args:
        current_status: Current status
        new_status: New status to transition to

    Returns:
        True if transition is valid

    Raises:
        HTTPException: If transition is invalid
    """
    valid_transitions = {
        'WAITING': {'OFFERED', 'LEFT'},
        'OFFERED': {'ACCEPTED', 'DECLINED', 'EXPIRED', 'LEFT'},
        'ACCEPTED': set(),  # Terminal state
        'DECLINED': set(),  # Terminal state
        'EXPIRED': set(),   # Terminal state
        'LEFT': set(),      # Terminal state
    }

    allowed = valid_transitions.get(current_status, set())

    if new_status not in allowed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid status transition: {current_status} → {new_status}"
        )

    return True
