from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
import pytest

from app.core.config import settings
from tests.utils.venue import create_random_venue

# NOTE: You will need a testing utility to create JWTs for test users.
# This is a placeholder for that function.
from tests.utils.auth import get_user_authentication_headers


def test_create_venue(client: TestClient, db: Session) -> None:
    """
    Tests creating a new venue successfully.
    """
    headers = get_user_authentication_headers(db, org_id="org_test_1")
    data = {"name": "Test Convention Center", "address": "123 Test St"}

    response = client.post(
        "/api/v1/organizations/org_test_1/venues", headers=headers, json=data
    )

    assert response.status_code == 201
    content = response.json()
    assert content["name"] == data["name"]
    assert content["address"] == data["address"]
    assert "id" in content
    assert content["organization_id"] == "org_test_1"


def test_list_venues(client: TestClient, db: Session) -> None:
    """
    Tests retrieving a list of venues for an organization.
    """
    headers = get_user_authentication_headers(db, org_id="org_test_1")
    # Create a venue first to ensure the list is not empty
    create_random_venue(db, org_id="org_test_1")

    response = client.get("/api/v1/organizations/org_test_1/venues", headers=headers)

    assert response.status_code == 200
    content = response.json()
    assert isinstance(content, list)
    assert len(content) > 0
    assert content[0]["organization_id"] == "org_test_1"


def test_update_venue(client: TestClient, db: Session) -> None:
    """
    Tests updating an existing venue.
    """
    headers = get_user_authentication_headers(db, org_id="org_test_1")
    venue = create_random_venue(db, org_id="org_test_1")
    data = {"name": "Updated Venue Name"}

    response = client.patch(
        f"/api/v1/organizations/org_test_1/venues/{venue.id}",
        headers=headers,
        json=data,
    )

    assert response.status_code == 200
    content = response.json()
    assert content["name"] == "Updated Venue Name"
    assert content["id"] == venue.id


def test_delete_venue(client: TestClient, db: Session) -> None:
    """
    Tests soft-deleting a venue.
    """
    headers = get_user_authentication_headers(db, org_id="org_test_1")
    venue = create_random_venue(db, org_id="org_test_1")

    response = client.delete(
        f"/api/v1/organizations/org_test_1/venues/{venue.id}", headers=headers
    )

    assert response.status_code == 204
    # Verify it was soft-deleted
    db_obj = crud_venue.venue.get(db, id=venue.id)
    assert db_obj.is_archived is True


def test_fail_to_access_venue_from_another_org(client: TestClient, db: Session) -> None:
    """
    Tests that a user from one org cannot access a venue from another.
    """
    # User is from org_test_1
    headers = get_user_authentication_headers(db, org_id="org_test_1")
    # Venue is in org_test_2
    venue = create_random_venue(db, org_id="org_test_2")

    response = client.get(
        f"/api/v1/organizations/org_test_2/venues/{venue.id}", headers=headers
    )

    # The authorization check in the endpoint should raise a 403 Forbidden
    assert response.status_code == 403
