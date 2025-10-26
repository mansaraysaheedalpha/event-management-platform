# app/features/booking/service.py
from typing import Dict, Any
from datetime import datetime
import random
import string
from .schemas import BookingCallRequest, BookingCallResponse


def _get_speaker_from_db(speaker_id: str) -> Dict[str, Any]:
    """Simulates fetching speaker data from a database."""
    # Mock speaker database
    speakers = {
        "spk_1": {"id": "spk_1", "name": "Dr. Eva Rostova", "rate_per_hour": 500},
        "spk_2": {"id": "spk_2", "name": "John CEO", "rate_per_hour": 1000},
        "spk_3": {"id": "spk_3", "name": "DevOps Dan", "rate_per_hour": 300},
        "spk_4": {"id": "spk_4", "name": "Anna Coder", "rate_per_hour": 400},
    }
    return speakers.get(speaker_id, {"id": speaker_id, "name": "Unknown Speaker", "rate_per_hour": 0})


def _generate_booking_id() -> str:
    """Generate a unique booking ID."""
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    random_suffix = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
    return f"BK-{timestamp}-{random_suffix}"


def _generate_confirmation_code() -> str:
    """Generate a confirmation code."""
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))


def _generate_meeting_link(booking_id: str) -> str:
    """Generate a mock video meeting link."""
    return f"https://meet.example.com/call/{booking_id}"


def book_speaker_call(request: BookingCallRequest) -> BookingCallResponse:
    """
    Books a call with a speaker.
    
    This is a simulated implementation that would integrate with:
    - Calendar/scheduling system
    - Payment processing
    - Video conferencing platform
    - Notification service
    """
    # Fetch speaker information
    speaker = _get_speaker_from_db(request.speaker_id)
    
    # Generate booking details
    booking_id = _generate_booking_id()
    confirmation_code = _generate_confirmation_code()
    meeting_link = _generate_meeting_link(booking_id)
    
    # Calculate estimated cost based on duration
    hourly_rate = speaker.get("rate_per_hour", 0)
    estimated_cost = (hourly_rate / 60) * request.duration_minutes if hourly_rate > 0 else None
    
    # In a real implementation, this would:
    # 1. Check speaker availability
    # 2. Reserve the time slot
    # 3. Process payment or create invoice
    # 4. Send confirmation emails
    # 5. Create calendar events
    # 6. Generate video meeting link
    
    # For now, we'll assume the booking is confirmed
    status = "confirmed"
    message = f"Your call with {speaker['name']} has been confirmed! You will receive a confirmation email shortly."
    
    return BookingCallResponse(
        booking_id=booking_id,
        status=status,
        speaker_id=speaker["id"],
        speaker_name=speaker["name"],
        scheduled_time=request.preferred_date,
        duration_minutes=request.duration_minutes,
        meeting_link=meeting_link,
        confirmation_code=confirmation_code,
        estimated_cost=estimated_cost,
        message=message
    )
