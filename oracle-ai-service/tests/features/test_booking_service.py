# tests/features/test_booking_service.py

import pytest
from app.features.booking.service import book_speaker_call
from app.features.booking.schemas import BookingCallRequest


def test_book_speaker_call_returns_confirmation(mocker):
    """
    Tests that booking a call returns a valid confirmation with all required details.
    """
    # 1. Arrange
    request = BookingCallRequest(
        user_id="user_123",
        speaker_id="spk_1",
        event_id="evt_456",
        preferred_date="2025-11-01T14:00:00Z",
        duration_minutes=60,
        topic="AI Strategy Discussion",
        notes="Looking forward to discussing AI implementation"
    )

    # 2. Act
    response = book_speaker_call(request)

    # 3. Assert
    assert response.booking_id is not None
    assert response.booking_id.startswith("BK-")
    assert response.status == "confirmed"
    assert response.speaker_id == "spk_1"
    assert response.speaker_name == "Dr. Eva Rostova"
    assert response.scheduled_time == "2025-11-01T14:00:00Z"
    assert response.duration_minutes == 60
    assert response.meeting_link is not None
    assert response.meeting_link.startswith("https://meet.example.com/call/")
    assert response.confirmation_code is not None
    assert len(response.confirmation_code) == 8
    assert response.estimated_cost is not None
    assert response.estimated_cost == pytest.approx(500.0)  # Dr. Eva's rate: $500/hr for 60 minutes
    assert "confirmed" in response.message.lower()


def test_book_speaker_call_calculates_cost_correctly(mocker):
    """
    Tests that the booking service correctly calculates the cost based on duration.
    """
    # 1. Arrange - Book a 30-minute call
    request = BookingCallRequest(
        user_id="user_123",
        speaker_id="spk_2",  # John CEO - $1000/hr
        event_id="evt_456",
        preferred_date="2025-11-01T14:00:00Z",
        duration_minutes=30,
        topic="Executive Leadership Discussion"
    )

    # 2. Act
    response = book_speaker_call(request)

    # 3. Assert
    # For 30 minutes at $1000/hr, cost should be $500
    assert response.estimated_cost == pytest.approx(500.0)
    assert response.speaker_name == "John CEO"


def test_book_speaker_call_unknown_speaker(mocker):
    """
    Tests that booking handles unknown speakers gracefully.
    """
    # 1. Arrange
    request = BookingCallRequest(
        user_id="user_123",
        speaker_id="spk_unknown",
        event_id="evt_456",
        preferred_date="2025-11-01T14:00:00Z",
        duration_minutes=60,
        topic="General Discussion"
    )

    # 2. Act
    response = book_speaker_call(request)

    # 3. Assert
    assert response.booking_id is not None
    assert response.status == "confirmed"
    assert response.speaker_name == "Unknown Speaker"
    # Unknown speakers have no rate, so no cost
    assert response.estimated_cost is None
