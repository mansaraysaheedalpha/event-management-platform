# app/graphql/rsvp_types.py
"""
GraphQL types for Session RSVP system.
"""

import strawberry
from typing import Optional
from datetime import datetime
from enum import Enum


@strawberry.enum
class RsvpStatus(str, Enum):
    CONFIRMED = "CONFIRMED"
    CANCELLED = "CANCELLED"


@strawberry.type
class SessionRsvpType:
    """A user's RSVP for a session."""
    id: str
    session_id: str
    user_id: str
    event_id: str
    status: RsvpStatus
    rsvp_at: datetime
    cancelled_at: Optional[datetime]


@strawberry.type
class RsvpToSessionResponse:
    """Response when a user RSVPs to a session."""
    success: bool
    rsvp: Optional[SessionRsvpType]
    message: Optional[str]


@strawberry.type
class CancelSessionRsvpResponse:
    """Response when a user cancels their session RSVP."""
    success: bool
    message: Optional[str]


@strawberry.type
class MyScheduleSessionType:
    """A session in the user's schedule (includes session details + RSVP info)."""
    rsvp_id: str
    rsvp_status: RsvpStatus
    rsvp_at: datetime
    # Session fields
    session_id: str
    title: str
    start_time: datetime
    end_time: datetime
    session_type: Optional[str]
    speakers: Optional[str]  # Comma-separated speaker names


@strawberry.input
class RsvpToSessionInput:
    session_id: str


@strawberry.input
class CancelSessionRsvpInput:
    session_id: str
