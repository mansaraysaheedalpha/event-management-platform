"""Pydantic schemas for Session Reminder operations."""

from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field
from enum import Enum


class ReminderType(str, Enum):
    """Supported reminder interval types."""
    FIFTEEN_MIN = "15_MIN"
    FIVE_MIN = "5_MIN"


class EmailStatus(str, Enum):
    """Email delivery status tracking."""
    QUEUED = "QUEUED"
    SENT = "SENT"
    DELIVERED = "DELIVERED"
    FAILED = "FAILED"


class SessionReminderBase(BaseModel):
    """Base schema with shared fields."""
    registration_id: str
    session_id: str
    user_id: Optional[str] = None
    event_id: str
    reminder_type: ReminderType


class SessionReminderCreate(SessionReminderBase):
    """Schema for creating a new session reminder."""
    scheduled_at: datetime


class SessionReminderUpdate(BaseModel):
    """Schema for updating reminder status."""
    email_status: Optional[EmailStatus] = None
    sent_at: Optional[datetime] = None
    magic_link_token_jti: Optional[str] = None
    error_message: Optional[str] = None


class SessionReminder(SessionReminderBase):
    """Response schema for session reminder."""
    id: str
    scheduled_at: datetime
    sent_at: Optional[datetime] = None
    magic_link_token_jti: Optional[str] = None
    email_status: EmailStatus
    error_message: Optional[str] = None

    model_config = {"from_attributes": True}


class SessionReminderWithDetails(SessionReminder):
    """Extended schema with session and registration details."""
    session_title: Optional[str] = None
    event_name: Optional[str] = None
    attendee_email: Optional[str] = None
    attendee_name: Optional[str] = None


# Internal data transfer objects for background tasks
class ReminderTaskData(BaseModel):
    """Data passed to reminder email task."""
    reminder_id: str
    user_id: Optional[str]
    user_email: str
    user_name: str
    session_id: str
    session_title: str
    session_start: str  # ISO format
    session_end: str  # ISO format
    event_id: str
    event_name: str
    registration_id: str
    reminder_type: str
    speakers: List[str] = Field(default_factory=list)


class ReminderScheduleConfig(BaseModel):
    """Configuration for reminder intervals."""
    intervals_minutes: List[int] = Field(
        default=[15, 5],
        description="Minutes before session to send reminders"
    )
    window_tolerance_minutes: int = Field(
        default=1,
        description="Tolerance window for scheduling (±minutes)"
    )
