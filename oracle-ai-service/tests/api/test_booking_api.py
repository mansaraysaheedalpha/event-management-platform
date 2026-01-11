# tests/api/test_booking_api.py

from fastapi.testclient import TestClient
from app.main import app

# Create a client to make requests to our app
client = TestClient(app)


def test_booking_call_endpoint_success():
    """
    Tests the full request-response cycle for the booking call endpoint.
    """
    request_payload = {
        "user_id": "user_123",
        "speaker_id": "spk_1",
        "event_id": "evt_456",
        "preferred_date": "2025-11-01T14:00:00Z",
        "duration_minutes": 60,
        "topic": "AI Strategy Discussion",
        "notes": "Looking forward to discussing AI implementation"
    }

    response = client.post("/oracle/booking/call", json=request_payload)

    assert response.status_code == 200

    response_data = response.json()
    assert "booking_id" in response_data
    assert response_data["booking_id"].startswith("BK-")
    assert response_data["status"] == "confirmed"
    assert response_data["speaker_id"] == "spk_1"
    assert response_data["speaker_name"] == "Dr. Eva Rostova"
    assert response_data["scheduled_time"] == "2025-11-01T14:00:00Z"
    assert response_data["duration_minutes"] == 60
    assert "meeting_link" in response_data
    assert "confirmation_code" in response_data
    assert len(response_data["confirmation_code"]) == 8
    assert abs(response_data["estimated_cost"] - 500.0) < 0.01  # Allow for floating point precision
    assert "confirmed" in response_data["message"].lower()


def test_booking_call_endpoint_validation_error():
    """
    Tests that the endpoint handles invalid request payloads gracefully.
    """
    invalid_payload = {
        # Missing required fields
        "speaker_id": "spk_1",
        "event_id": "evt_456"
    }

    response = client.post("/oracle/booking/call", json=invalid_payload)

    # FastAPI should return a 422 Unprocessable Entity for Pydantic validation errors
    assert response.status_code == 422


def test_booking_call_with_minimal_data():
    """
    Tests booking with minimal required fields (without optional notes).
    """
    request_payload = {
        "user_id": "user_456",
        "speaker_id": "spk_3",
        "event_id": "evt_789",
        "preferred_date": "2025-11-15T10:00:00Z",
        "duration_minutes": 30,
        "topic": "DevOps Best Practices"
    }

    response = client.post("/oracle/booking/call", json=request_payload)

    assert response.status_code == 200

    response_data = response.json()
    assert response_data["speaker_name"] == "DevOps Dan"
    assert response_data["duration_minutes"] == 30
    # DevOps Dan's rate is $300/hr, so 30 minutes = $150
    assert abs(response_data["estimated_cost"] - 150.0) < 0.01  # Allow for floating point precision
