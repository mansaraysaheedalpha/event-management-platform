"""Pydantic schemas for Email Preference operations."""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class EmailPreferenceBase(BaseModel):
    """Base schema with shared fields."""
    pre_event_agenda: bool = True
    pre_event_networking: bool = True
    session_reminders: bool = True


class EmailPreferenceCreate(EmailPreferenceBase):
    """Schema for creating email preferences."""
    user_id: str
    event_id: Optional[str] = None  # None = global preference


class EmailPreferenceUpdate(BaseModel):
    """Schema for updating email preferences (partial update)."""
    pre_event_agenda: Optional[bool] = None
    pre_event_networking: Optional[bool] = None
    session_reminders: Optional[bool] = None


class EmailPreference(EmailPreferenceBase):
    """Response schema for email preference."""
    id: str
    user_id: str
    event_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class EmailPreferencePublic(BaseModel):
    """Public response schema (without user_id)."""
    pre_event_agenda: bool
    pre_event_networking: bool
    session_reminders: bool
    event_id: Optional[str] = None

    model_config = {"from_attributes": True}
