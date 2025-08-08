from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from app.crud import crud_venue
from app.schemas.venue import VenueCreate


def test_create_venue_api(client: TestClient):
    """
    Tests the successful creation of a new venue.
    """
    # ARRANGE
    venue_data = {"name": "Grand Convention Center", "address": "123 Main Street"}

    # ACT
    response = client.post("/api/v1/organizations/acme-corp/venues", json=venue_data)

    # ASSERT
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Grand Convention Center"
    assert data["organization_id"] == "acme-corp"


def test_list_venues_api(client: TestClient, db_session: Session):
    """
    Tests listing all venues for a specific organization.
    """
    # ARRANGE: Create a couple of venues
    crud_venue.venue.create_with_organization(
        db_session, obj_in=VenueCreate(name="Acme Venue"), org_id="acme-corp"
    )
    crud_venue.venue.create_with_organization(
        db_session, obj_in=VenueCreate(name="Other Corp Venue"), org_id="other-corp"
    )

    # ACT
    response = client.get("/api/v1/organizations/acme-corp/venues")

    # ASSERT
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["name"] == "Acme Venue"
