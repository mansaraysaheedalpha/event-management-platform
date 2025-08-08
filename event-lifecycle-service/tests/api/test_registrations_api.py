from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from app.crud import crud_event, crud_registration
from app.schemas.event import EventCreate
from datetime import datetime, timezone


def test_create_registration_for_guest_api(client: TestClient, db_session: Session):
    """
    Tests creating a new registration for a guest user.
    """
    # ARRANGE: Create an event to register for
    test_event = crud_event.event.create_with_organization(
        db_session,
        obj_in=EventCreate(
            name="Test Event for Reg",
            start_date=datetime.now(timezone.utc),
            end_date=datetime.now(timezone.utc),
        ),
        org_id="acme-corp",
    )
    registration_data = {
        "first_name": "Guest",
        "last_name": "User",
        "email": "guest@example.com",
    }

    # ACT
    response = client.post(
        f"/api/v1/organizations/acme-corp/events/{test_event.id}/registrations",
        json=registration_data,
    )

    # ASSERT
    assert response.status_code == 201
    data = response.json()
    assert data["guest_name"] == "Guest User"
    assert data["guest_email"] == "guest@example.com"
    assert data["status"] == "confirmed"


def test_prevent_duplicate_registration_api(client: TestClient, db_session: Session):
    """
    Tests that the API prevents the same guest from registering twice.
    """
    # ARRANGE: Create an event and an initial registration
    test_event = crud_event.event.create_with_organization(
        db_session,
        obj_in=EventCreate(
            name="Test Event for Duplicates",
            start_date=datetime.now(timezone.utc),
            end_date=datetime.now(timezone.utc),
        ),
        org_id="acme-corp",
    )
    registration_data = {
        "first_name": "Duplicate",
        "last_name": "Guest",
        "email": "duplicate@example.com",
    }
    # First registration should succeed
    client.post(
        f"/api/v1/organizations/acme-corp/events/{test_event.id}/registrations",
        json=registration_data,
    )

    # ACT: Attempt to register the same guest again
    response = client.post(
        f"/api/v1/organizations/acme-corp/events/{test_event.id}/registrations",
        json=registration_data,
    )

    # ASSERT
    assert response.status_code == 409  # 409 Conflict
    data = response.json()
    assert "already registered" in data["detail"]
