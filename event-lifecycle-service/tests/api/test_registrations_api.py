from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from tests.utils.auth import get_user_authentication_headers
from tests.utils.event import create_random_event


def test_create_registration_for_guest(client: TestClient, db: Session) -> None:
    headers = get_user_authentication_headers(db, org_id="org_reg_test")
    event = create_random_event(db, org_id="org_reg_test")
    data = {"first_name": "Test", "last_name": "User", "email": "guest@example.com"}

    response = client.post(
        f"/api/v1/organizations/org_reg_test/events/{event.id}/registrations",
        headers=headers,
        json=data,
    )

    assert response.status_code == 201
    content = response.json()
    assert content["guest_email"] == data["email"]
    assert content["user_id"] is None
    assert "ticket_code" in content


def test_fail_to_create_duplicate_registration(client: TestClient, db: Session) -> None:
    headers = get_user_authentication_headers(db, org_id="org_reg_test")
    event = create_random_event(db, org_id="org_reg_test")
    data = {
        "email": "duplicate@example.com",
        "first_name": "Guest",
        "last_name": "User",
    }

    # First registration should succeed
    response1 = client.post(
        f"/api/v1/organizations/org_reg_test/events/{event.id}/registrations",
        headers=headers,
        json=data,
    )
    assert response1.status_code == 201

    # Second attempt should fail with a 409 Conflict
    response2 = client.post(
        f"/api/v1/organizations/org_reg_test/events/{event.id}/registrations",
        headers=headers,
        json=data,
    )
    assert response2.status_code == 409
