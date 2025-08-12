from fastapi.testclient import TestClient
from app.crud import crud_event
from app.schemas.event import EventCreate
from datetime import datetime, timedelta, timezone

def test_create_event_api(client: TestClient):
    """
    Tests the POST /organizations/{orgId}/events API endpoint.
    """
    request_data = {
        "name": "API Test Event",
        "start_date": "2025-10-26T10:00:00Z",
        "end_date": "2025-10-28T18:00:00Z",
    }
    response = client.post("/api/v1/organizations/acme-corp/events", json=request_data)

    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "API Test Event"
    assert data["organization_id"] == "acme-corp"


def test_list_events_api(client: TestClient, db_session):
    """
    Tests the GET /organizations/{orgId}/events API endpoint.
    """
    # ARRANGE: Create a few events in the database first
    crud_event.event.create_with_organization(
        db_session,
        obj_in=EventCreate(
            name="Event 1", start_date=datetime.utcnow(), end_date=datetime.utcnow()
        ),
        org_id="acme-corp",
    )
    crud_event.event.create_with_organization(
        db_session,
        obj_in=EventCreate(
            name="Event 2", start_date=datetime.utcnow(), end_date=datetime.utcnow()
        ),
        org_id="acme-corp",
    )
    crud_event.event.create_with_organization(
        db_session,
        obj_in=EventCreate(
            name="Other Corp Event",
            start_date=datetime.utcnow(),
            end_date=datetime.utcnow(),
        ),
        org_id="other-corp",
    )

    # ACT: Make the API request
    response = client.get("/api/v1/organizations/acme-corp/events")

    # ASSERT
    assert response.status_code == 200
    data = response.json()

    # We should only get the 2 events belonging to acme-corp
    assert len(data["data"]) == 2
    assert data["data"][0]["name"] == "Event 1"
    assert data["pagination"]["totalItems"] == 2


def test_get_event_by_id_api(client: TestClient, db_session):
    """
    Tests the GET /organizations/{orgId}/events/{eventId} API endpoint.
    """
    # ARRANGE: Create an event to fetch
    created_event = crud_event.event.create_with_organization(
        db_session,
        obj_in=EventCreate(
            name="Specific Event",
            start_date=datetime.now(timezone.utc),
            end_date=datetime.now(timezone.utc),
        ),
        org_id="acme-corp",
    )

    # ACT: Make the API request for the created event
    response = client.get(f"/api/v1/organizations/acme-corp/events/{created_event.id}")

    # ASSERT: Check for success
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Specific Event"
    assert data["id"] == created_event.id

    # ACT & ASSERT for a non-existent event
    response_not_found = client.get(
        f"/api/v1/organizations/acme-corp/events/evt_nonexistent"
    )
    assert response_not_found.status_code == 404


def test_update_event_api(client: TestClient, db_session):
    """
    Tests the PATCH /organizations/{orgId}/events/{eventId} API endpoint.
    """
    # ARRANGE: Create an event to update
    created_event = crud_event.event.create_with_organization(
        db_session,
        obj_in=EventCreate(
            name="Original Name",
            start_date=datetime.now(timezone.utc),
            end_date=datetime.now(timezone.utc),
        ),
        org_id="acme-corp",
    )
    update_data = {"name": "Updated Event Name"}

    # ACT: Make the API request to update the event
    response = client.patch(
        f"/api/v1/organizations/acme-corp/events/{created_event.id}", json=update_data
    )

    # ASSERT
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Updated Event Name"
    assert data["id"] == created_event.id


def test_delete_event_api(client: TestClient, db_session):
    """
    Tests the DELETE /organizations/{orgId}/events/{eventId} API endpoint.
    """
    # ARRANGE: Create an event to delete
    created_event = crud_event.event.create_with_organization(
        db_session,
        obj_in=EventCreate(
            name="To Be Deleted",
            start_date=datetime.now(timezone.utc),
            end_date=datetime.now(timezone.utc),
        ),
        org_id="acme-corp",
    )

    # ACT: Make the API request to delete the event
    response = client.delete(
        f"/api/v1/organizations/acme-corp/events/{created_event.id}"
    )

    # ASSERT: The request was successful
    assert response.status_code == 204

    # ASSERT: Verify the event is marked as archived in the database
    deleted_event = crud_event.event.get(db_session, id=created_event.id)
    assert deleted_event.is_archived is True
