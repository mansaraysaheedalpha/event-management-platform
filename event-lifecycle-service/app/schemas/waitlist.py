# app/schemas/waitlist.py
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


# ==================== Legacy/Simple Waitlist Schema ====================
# Used by the old waitlist implementation in crud_waitlist.py

class WaitlistEntry(BaseModel):
    """Simple waitlist entry (legacy/old implementation)"""
    id: str
    session_id: str
    user_id: str
    created_at: datetime

    class Config:
        from_attributes = True


# ==================== Request DTOs ====================

class WaitlistJoinRequest(BaseModel):
    """Request to join a session waitlist"""
    pass  # No additional fields needed, session_id from URL, user from auth


class AcceptOfferRequest(BaseModel):
    """Request to accept a waitlist offer"""
    join_token: str = Field(..., description="JWT token from waitlist offer")


# ==================== Response DTOs ====================

class WaitlistPositionResponse(BaseModel):
    """Current position in waitlist"""
    position: int = Field(..., description="Position in queue (1-indexed)")
    total: int = Field(..., description="Total users waiting")
    estimated_wait_minutes: Optional[int] = Field(None, description="Estimated wait time in minutes")
    priority_tier: str = Field(..., description="Priority tier: STANDARD, VIP, or PREMIUM")

    class Config:
        from_attributes = True


class WaitlistJoinResponse(BaseModel):
    """Response after joining waitlist"""
    id: str = Field(..., description="Waitlist entry ID")
    position: int = Field(..., description="Position in queue")
    total: int = Field(..., description="Total users waiting")
    message: str = Field(..., description="User-friendly message")

    class Config:
        from_attributes = True


class WaitlistEntryResponse(BaseModel):
    """Detailed waitlist entry information"""
    id: str
    session_id: str
    user_id: str
    priority_tier: str
    position: int
    status: str
    offer_token: Optional[str] = None
    offer_sent_at: Optional[datetime] = None
    offer_expires_at: Optional[datetime] = None
    offer_responded_at: Optional[datetime] = None
    joined_at: datetime
    left_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class AcceptOfferResponse(BaseModel):
    """Response after accepting offer"""
    success: bool = Field(..., description="Whether acceptance was successful")
    message: str = Field(..., description="User-friendly message")
    session_id: Optional[str] = Field(None, description="Session ID joined")

    class Config:
        from_attributes = True


# ==================== Event DTOs (for logging) ====================

class WaitlistEventCreate(BaseModel):
    """Create a waitlist event log entry"""
    waitlist_entry_id: str
    event_type: str = Field(..., description="Event type: JOINED, OFFERED, ACCEPTED, etc.")
    event_data: Optional[dict] = Field(default_factory=dict, description="Additional event data")


class WaitlistEventResponse(BaseModel):
    """Waitlist event log entry"""
    id: str
    waitlist_entry_id: str
    event_type: str
    event_data: Optional[dict] = None
    created_at: datetime

    class Config:
        from_attributes = True
