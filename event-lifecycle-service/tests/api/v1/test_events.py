# tests/api/v1/test_events.py


from fastapi.testclient import TestClient
from unittest.mock import MagicMock
from datetime import datetime, timezone

from app.schemas.event import Event as EventSchema, EventStatus

# Mocks
crud_event_mock = MagicMock()
crud_domain_event_mock = MagicMock()


class MockTokenPayload:
    def __init__(self, sub, org_id):
        self.sub = sub
        self.org_id = org_id


def override_get_current_user():
    return MockTokenPayload(sub="user_123", org_id="org_abc")


# Helper function to apply mocks for this test file
def apply_mocks(monkeypatch):
    monkeypatch.setattr("app.api.v1.endpoints.events.crud_event", crud_event_mock)
    monkeypatch.setattr(
        "app.api.v1.endpoints.events.crud_domain_event", crud_domain_event_mock
    )


# --- CREATE ---
def test_create_event_success(monkeypatch, test_client: TestClient):
    apply_mocks(monkeypatch)
    event_data = {
        "name": "Test Event",
        "start_date": "2025-10-10T10:00:00Z",
        "end_date": "2025-10-10T12:00:00Z",
    }
    return_event = EventSchema(
        id="evt_1",
        organization_id="org_abc",
        name="Test Event",
        version=1,
        status=EventStatus.draft,
        start_date=datetime.now(timezone.utc),
        end_date=datetime.now(timezone.utc),
        is_public=False,
    )
    crud_event_mock.event.create_with_organization.return_value = return_event
    response = test_client.post("/api/v1/organizations/org_abc/events", json=event_data)
    assert response.status_code == 201
    assert response.json()["name"] == "Test Event"


def test_create_event_forbidden(monkeypatch, test_client):
    apply_mocks(monkeypatch)
    # **FIX**: Provide a valid request body to get past the 422 validation error
    # so we can properly test the 403 authorization logic.
    valid_body = {
        "name": "Test Event",
        "start_date": "2025-10-10T10:00:00Z",
        "end_date": "2025-10-10T12:00:00Z",
    }
    response = test_client.post("/api/v1/organizations/org_xyz/events", json=valid_body)
    assert response.status_code == 403


# --- READ ---
def test_list_events_success(monkeypatch, test_client: TestClient):
    apply_mocks(monkeypatch)
    crud_event_mock.event.get_multi_by_organization.return_value = [
        EventSchema(
            id="evt_1",
            name="Event 1",
            organization_id="org_abc",
            version=1,
            status=EventStatus.draft,
            start_date=datetime.now(timezone.utc),
            end_date=datetime.now(timezone.utc),
            is_public=False,
        )
    ]
    crud_event_mock.event.get_events_count.return_value = 1
    response = test_client.get("/api/v1/organizations/org_abc/events")
    assert response.status_code == 200
    assert response.json()["data"][0]["name"] == "Event 1"
    assert response.json()["pagination"]["totalItems"] == 1


def test_get_event_by_id_success(monkeypatch, test_client: TestClient):
    apply_mocks(monkeypatch)
    mock_event = EventSchema(
        id="evt_1",
        name="Event 1",
        organization_id="org_abc",
        version=1,
        status=EventStatus.draft,
        start_date=datetime.now(timezone.utc),
        end_date=datetime.now(timezone.utc),
        is_public=False,
    )
    crud_event_mock.event.get.return_value = mock_event
    response = test_client.get("/api/v1/organizations/org_abc/events/evt_1")
    assert response.status_code == 200
    assert response.json()["id"] == "evt_1"


def test_get_event_not_found(monkeypatch, test_client: TestClient):
    apply_mocks(monkeypatch)
    crud_event_mock.event.get.return_value = None
    response = test_client.get("/api/v1/organizations/org_abc/events/evt_nonexistent")
    assert response.status_code == 404


# --- UPDATE ---
def test_update_event_success(monkeypatch, test_client: TestClient):
    apply_mocks(monkeypatch)
    mock_event = MagicMock(organization_id="org_abc")
    crud_event_mock.event.get.return_value = mock_event
    updated_event = EventSchema(
        id="evt_1",
        name="Updated Name",
        organization_id="org_abc",
        version=1,
        status=EventStatus.draft,
        start_date=datetime.now(timezone.utc),
        end_date=datetime.now(timezone.utc),
        is_public=False,
    )
    crud_event_mock.event.update.return_value = updated_event
    response = test_client.patch(
        "/api/v1/organizations/org_abc/events/evt_1", json={"name": "Updated Name"}
    )
    assert response.status_code == 200
    assert response.json()["name"] == "Updated Name"


# --- DELETE ---
def test_delete_event_success(monkeypatch, test_client: TestClient):
    apply_mocks(monkeypatch)
    mock_event = MagicMock(organization_id="org_abc")
    crud_event_mock.event.get.return_value = mock_event
    response = test_client.delete("/api/v1/organizations/org_abc/events/evt_1")
    assert response.status_code == 204
    crud_event_mock.event.archive.assert_called_once()


# --- PUBLISH ---
def test_publish_event_success(monkeypatch, test_client: TestClient):
    apply_mocks(monkeypatch)
    mock_event = MagicMock(organization_id="org_abc", status="draft")
    crud_event_mock.event.get.return_value = mock_event
    published_event = EventSchema(
        id="evt_1",
        name="Published Event",
        organization_id="org_abc",
        version=1,
        status=EventStatus.published,
        start_date=datetime.now(timezone.utc),
        end_date=datetime.now(timezone.utc),
        is_public=False,
    )
    crud_event_mock.event.publish.return_value = published_event
    response = test_client.post("/api/v1/organizations/org_abc/events/evt_1/publish")
    assert response.status_code == 200
    assert response.json()["status"] == "published"
