from fastapi.testclient import TestClient
from sqlalchemy.orm import Session


def test_event_lifecycle(test_client_e2e: TestClient, db_session_e2e: Session):
    """
    Tests the full CRUD lifecycle of an Event against a live test database.
    """
    org_id = "org_abc"

    # 1. CREATE an Event
    event_data = {
        "name": "E2E Test Event",
        "start_date": "2025-12-01T10:00:00Z",
        "end_date": "2025-12-01T12:00:00Z",
    }
    response = test_client_e2e.post(
        f"/api/v1/organizations/{org_id}/events", json=event_data
    )
    assert response.status_code == 201

    created_event = response.json()
    assert created_event["name"] == "E2E Test Event"
    assert created_event["status"] == "draft"
    event_id = created_event["id"]

    # 2. READ the Event (List)
    response = test_client_e2e.get(f"/api/v1/organizations/{org_id}/events")
    assert response.status_code == 200
    assert len(response.json()["data"]) == 1
    assert response.json()["data"][0]["id"] == event_id

    # 3. UPDATE the Event
    update_data = {"description": "This is an updated description."}
    response = test_client_e2e.patch(
        f"/api/v1/organizations/{org_id}/events/{event_id}", json=update_data
    )
    assert response.status_code == 200
    assert response.json()["description"] == "This is an updated description."

    # 4. PUBLISH the Event
    response = test_client_e2e.post(
        f"/api/v1/organizations/{org_id}/events/{event_id}/publish"
    )
    assert response.status_code == 200
    assert response.json()["status"] == "published"

    # 5. READ the Event History
    response = test_client_e2e.get(
        f"/api/v1/organizations/{org_id}/events/{event_id}/history"
    )
    assert response.status_code == 200
    history = response.json()
    assert len(history) > 0
    assert any(log["event_type"] == "EventPublished" for log in history)

    # 6. DELETE the Event
    response = test_client_e2e.delete(
        f"/api/v1/organizations/{org_id}/events/{event_id}"
    )
    assert response.status_code == 204

    # 7. Verify it's gone from the list
    response = test_client_e2e.get(f"/api/v1/organizations/{org_id}/events")
    assert response.status_code == 200
    assert len(response.json()["data"]) == 0
