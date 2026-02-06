"""Pydantic schemas for Pre-Event Email operations."""

from datetime import datetime, date
from typing import Optional, List
from pydantic import BaseModel, Field
from enum import Enum


class PreEventEmailType(str, Enum):
    """Types of pre-event emails."""
    AGENDA = "AGENDA"
    NETWORKING = "NETWORKING"


class PreEventEmailStatus(str, Enum):
    """Email delivery status tracking."""
    QUEUED = "QUEUED"
    SENT = "SENT"
    DELIVERED = "DELIVERED"
    FAILED = "FAILED"


# Data classes for email content
class SessionRecommendation(BaseModel):
    """Session data for pre-event email content."""
    session_id: str
    title: str
    start_time: str
    end_time: str
    room: Optional[str] = None
    speakers: List[str] = Field(default_factory=list)
    match_reason: Optional[str] = None


class PersonRecommendation(BaseModel):
    """Person recommendation for networking email."""
    user_id: str
    name: str
    role: Optional[str] = None
    company: Optional[str] = None
    avatar_url: Optional[str] = None
    match_score: int = Field(..., ge=0, le=100)
    reasons: List[str] = Field(default_factory=list)
    conversation_starters: List[str] = Field(default_factory=list)


class BoothRecommendation(BaseModel):
    """Booth recommendation for pre-event email."""
    booth_id: str
    name: str
    tagline: Optional[str] = None
    logo_url: Optional[str] = None
    tier: str
    match_reason: Optional[str] = None


class PreEventEmailContent(BaseModel):
    """Complete pre-event email content payload."""
    attendee_name: str
    event_name: str
    event_date: str
    event_location: Optional[str] = None
    registered_sessions: List[SessionRecommendation] = Field(default_factory=list)
    recommended_sessions: List[SessionRecommendation] = Field(default_factory=list)
    people: List[PersonRecommendation] = Field(default_factory=list)
    booths: List[BoothRecommendation] = Field(default_factory=list)
    event_url: str


# CRUD schemas
class PreEventEmailBase(BaseModel):
    """Base schema with shared fields."""
    registration_id: str
    event_id: str
    user_id: Optional[str] = None
    email_type: PreEventEmailType
    email_date: date


class PreEventEmailCreate(PreEventEmailBase):
    """Schema for creating a pre-event email record."""
    scheduled_at: datetime


class PreEventEmailUpdate(BaseModel):
    """Schema for updating email status."""
    email_status: Optional[PreEventEmailStatus] = None
    sent_at: Optional[datetime] = None
    resend_message_id: Optional[str] = None
    error_message: Optional[str] = None


class PreEventEmail(PreEventEmailBase):
    """Response schema for pre-event email."""
    id: str
    scheduled_at: datetime
    sent_at: Optional[datetime] = None
    email_status: PreEventEmailStatus
    resend_message_id: Optional[str] = None
    error_message: Optional[str] = None

    model_config = {"from_attributes": True}


class PreEventEmailWithDetails(PreEventEmail):
    """Extended schema with registration and event details."""
    attendee_email: Optional[str] = None
    attendee_name: Optional[str] = None
    event_name: Optional[str] = None


# Internal DTOs for background tasks
class PreEventEmailTaskData(BaseModel):
    """Data passed to pre-event email sending task."""
    email_record_id: str
    registration_id: str
    user_id: Optional[str]
    user_email: str
    user_name: str
    event_id: str
    event_name: str
    event_date: str
    event_location: Optional[str] = None
    email_type: str
