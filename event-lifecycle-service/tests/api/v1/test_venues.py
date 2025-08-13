# tests/api/v1/test_venues.py

from fastapi.testclient import TestClient
from unittest.mock import MagicMock

from app.schemas.venue import Venue as VenueSchema

# Mocks
crud_venue_mock = MagicMock()


class MockTokenPayload:
    def __init__(self, sub, org_id):
        self.sub = sub
        self.org_id = org_id


def override_get_current_user():
    return MockTokenPayload(sub="user_123", org_id="org_abc")


def test_create_venue(monkeypatch, test_client: TestClient):
    monkeypatch.setattr("app.api.v1.endpoints.venues.crud_venue", crud_venue_mock)

    venue_data = {"name": "Main Hall", "address": "123 Event St"}
    return_venue = VenueSchema(
        id="ven_1", organization_id="org_abc", is_archived=False, **venue_data
    )
    crud_venue_mock.venue.create_with_organization.return_value = return_venue

    response = test_client.post("/api/v1/organizations/org_abc/venues", json=venue_data)

    assert response.status_code == 201
    assert response.json()["name"] == "Main Hall"


def test_get_venue_not_found(monkeypatch, test_client: TestClient):
    monkeypatch.setattr("app.api.v1.endpoints.venues.crud_venue", crud_venue_mock)
    crud_venue_mock.venue.get.return_value = None

    response = test_client.get("/api/v1/organizations/org_abc/venues/ven_nonexistent")

    assert response.status_code == 404
    assert response.json()["detail"] == "Venue not found"
