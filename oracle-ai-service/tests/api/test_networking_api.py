# tests/api/test_networking_api.py

from fastapi.testclient import TestClient
from app.main import app

# Create a client to make requests to our app
client = TestClient(app)


def test_matchmaking_endpoint_success():
    """
    Tests the full request-response cycle for the matchmaking endpoint.
    """
    request_payload = {
        "primary_user": {
            "user_id": "user_a",
            "interests": ["Cloud", "Security", "Python"],
        },
        "other_users": [
            {"user_id": "user_b", "interests": ["Security", "DevOps"]},
            {"user_id": "user_c", "interests": ["Python", "Cloud", "AI"]},
        ],
        "max_matches": 5,
    }

    response = client.post("/oracle/networking/matchmaking", json=request_payload)

    assert response.status_code == 200

    response_data = response.json()
    assert "matches" in response_data
    assert len(response_data["matches"]) == 2

    # user_c is the better match (2/4 = 0.5) vs user_b (1/4 = 0.25)
    assert response_data["matches"][0]["user_id"] == "user_c"
    assert response_data["matches"][0]["match_score"] == 0.5
    assert response_data["matches"][1]["user_id"] == "user_b"
    assert response_data["matches"][1]["match_score"] == 0.25


def test_matchmaking_endpoint_validation_error():
    """
    Tests that the endpoint handles invalid request payloads gracefully.
    """
    invalid_payload = {
        "primary_user": {
            # Missing user_id and interests
        },
        "other_users": [],
        "max_matches": 5,
    }

    response = client.post("/oracle/networking/matchmaking", json=invalid_payload)

    # FastAPI should return a 422 Unprocessable Entity for Pydantic validation errors
    assert response.status_code == 422
