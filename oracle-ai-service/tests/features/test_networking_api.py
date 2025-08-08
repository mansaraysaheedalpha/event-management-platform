from fastapi.testclient import TestClient


def test_matchmaking_api_endpoint(client: TestClient):
    """
    Tests the full POST /networking/matchmaking API endpoint.
    """
    # ARRANGE: Set up the request payload
    request_data = {
        "primary_user": {
            "user_id": "user_A",
            "interests": ["python", "fastapi", "docker"],
        },
        "other_users": [
            {"user_id": "user_B", "interests": ["python", "fastapi", "react"]}
        ],
        "max_matches": 1,
    }

    # ACT: Make a POST request to the endpoint
    response = client.post("/oracle/networking/matchmaking", json=request_data)

    # ASSERT: Check the response
    assert response.status_code == 200

    response_data = response.json()
    assert len(response_data["matches"]) == 1

    match = response_data["matches"][0]
    assert match["user_id"] == "user_B"
    assert match["match_score"] == 0.5
    assert sorted(match["common_interests"]) == ["fastapi", "python"]
