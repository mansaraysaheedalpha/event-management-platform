# app/api/v1/endpoints/email_preferences.py
"""
Email preferences endpoints.

Allows users to manage their email notification preferences globally
or per-event.
"""

import re
from fastapi import APIRouter, Depends, HTTPException, Query, Path, status
from sqlalchemy.orm import Session
from typing import Annotated, Optional

from app.api import deps
from app.schemas.token import TokenPayload
from app.schemas.email_preference import (
    EmailPreference,
    EmailPreferenceUpdate,
    EmailPreferencePublic,
)
from app.crud.crud_email_preference import email_preference as crud_email_preference
from app.db.session import get_db
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

# UUID validation pattern for query/path parameters
UUID_REGEX = r'^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$'

# Type alias for validated event_id query parameter
EventIdQuery = Annotated[
    Optional[str],
    Query(pattern=UUID_REGEX, description="Event ID (UUID format)")
]

# Type alias for validated event_id path parameter
EventIdPath = Annotated[
    str,
    Path(pattern=UUID_REGEX, description="Event ID (UUID format)")
]


@router.get(
    "/me",
    response_model=EmailPreferencePublic,
    summary="Get current user's email preferences"
)
def get_my_preferences(
    event_id: EventIdQuery = None,
    *,
    db: Session = Depends(get_db),
    current_user: TokenPayload = Depends(deps.get_current_user),
):
    """
    Get current user's email preferences.

    If event_id is provided, returns event-specific preferences with global fallback.
    If event_id is not provided, returns global preferences.

    Returns default preferences (all enabled) if no preferences are saved.
    """
    if event_id:
        # Get effective preference for this event (with fallback)
        pref = crud_email_preference.get_effective_preference(
            db, user_id=current_user.sub, event_id=event_id
        )
    else:
        # Get global preference
        pref = crud_email_preference.get_by_user_and_event(
            db, user_id=current_user.sub, event_id=None
        )
        if not pref:
            # Return default preferences
            return EmailPreferencePublic(
                pre_event_agenda=True,
                pre_event_networking=True,
                session_reminders=True,
                event_id=None,
            )

    return pref


@router.put(
    "/me",
    response_model=EmailPreferencePublic,
    summary="Update current user's email preferences"
)
def update_my_preferences(
    preferences: EmailPreferenceUpdate,
    event_id: EventIdQuery = None,
    *,
    db: Session = Depends(get_db),
    current_user: TokenPayload = Depends(deps.get_current_user),
):
    """
    Update current user's email preferences.

    If event_id is provided, updates/creates event-specific preferences.
    If event_id is not provided, updates/creates global preferences.

    Only provided fields are updated (partial update).
    """
    result = crud_email_preference.upsert(
        db,
        user_id=current_user.sub,
        event_id=event_id,
        preferences=preferences,
    )

    if not result:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update preferences"
        )

    logger.info(
        f"User {current_user.sub} updated email preferences "
        f"(event_id={event_id})"
    )

    return result


@router.delete(
    "/me",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete event-specific preferences"
)
def delete_my_event_preferences(
    event_id: Annotated[str, Query(pattern=UUID_REGEX, description="Event ID (UUID format)")],
    *,
    db: Session = Depends(get_db),
    current_user: TokenPayload = Depends(deps.get_current_user),
):
    """
    Delete event-specific email preferences.

    After deletion, global preferences will apply for this event.
    Only event-specific preferences can be deleted (not global).
    """
    pref = crud_email_preference.get_by_user_and_event(
        db, user_id=current_user.sub, event_id=event_id
    )

    if not pref:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No event-specific preferences found"
        )

    db.delete(pref)
    db.commit()

    logger.info(
        f"User {current_user.sub} deleted email preferences for event {event_id}"
    )


@router.get(
    "/events/{event_id}",
    response_model=EmailPreferencePublic,
    summary="Get email preferences for a specific event"
)
def get_event_preferences(
    event_id: EventIdPath,
    *,
    db: Session = Depends(get_db),
    current_user: TokenPayload = Depends(deps.get_current_user),
):
    """
    Get email preferences for a specific event.

    Returns event-specific preferences with global fallback,
    or default preferences if none are saved.
    """
    pref = crud_email_preference.get_effective_preference(
        db, user_id=current_user.sub, event_id=event_id
    )

    return pref


@router.put(
    "/events/{event_id}",
    response_model=EmailPreferencePublic,
    summary="Update email preferences for a specific event"
)
def update_event_preferences(
    event_id: EventIdPath,
    preferences: EmailPreferenceUpdate,
    *,
    db: Session = Depends(get_db),
    current_user: TokenPayload = Depends(deps.get_current_user),
):
    """
    Update email preferences for a specific event.

    Creates event-specific preferences if they don't exist,
    otherwise updates existing preferences.
    """
    result = crud_email_preference.upsert(
        db,
        user_id=current_user.sub,
        event_id=event_id,
        preferences=preferences,
    )

    if not result:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update preferences"
        )

    logger.info(
        f"User {current_user.sub} updated email preferences for event {event_id}"
    )

    return result
