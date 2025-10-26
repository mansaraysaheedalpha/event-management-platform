# app/features/booking/schemas.py
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class BookingCallRequest(BaseModel):
    """Request to book a call with a speaker."""
    user_id: str = Field(..., description="ID of the user booking the call")
    speaker_id: str = Field(..., description="ID of the speaker to book")
    event_id: str = Field(..., description="ID of the event context")
    preferred_date: str = Field(..., description="Preferred date for the call (ISO format)")
    duration_minutes: int = Field(30, description="Desired call duration in minutes")
    topic: str = Field(..., description="Topic or purpose of the call")
    notes: Optional[str] = Field(None, description="Additional notes or requirements")


class BookingCallResponse(BaseModel):
    """Response after booking a call."""
    booking_id: str = Field(..., description="Unique booking confirmation ID")
    status: str = Field(..., description="Booking status (confirmed, pending, rejected)")
    speaker_id: str
    speaker_name: str
    scheduled_time: str = Field(..., description="Confirmed call time (ISO format)")
    duration_minutes: int
    meeting_link: Optional[str] = Field(None, description="Video call link if available")
    confirmation_code: str = Field(..., description="Booking confirmation code")
    estimated_cost: Optional[float] = Field(None, description="Estimated cost if applicable")
    message: str = Field(..., description="Confirmation or additional information message")
