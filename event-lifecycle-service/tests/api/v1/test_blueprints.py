# tests/api/v1/test_blueprints.py

from fastapi.testclient import TestClient
from unittest.mock import MagicMock
from datetime import datetime, timezone

from app.schemas.event import Event as EventSchema, EventStatus

crud_blueprint_mock = MagicMock()
crud_event_mock = MagicMock()


class MockTokenPayload:
    def __init__(self, sub, org_id):
        self.sub = sub
        self.org_id = org_id


def override_get_current_user():
    return MockTokenPayload(sub="user_123", org_id="org_abc")


def apply_mocks(monkeypatch):
    monkeypatch.setattr(
        "app.api.v1.endpoints.blueprints.crud_blueprint", crud_blueprint_mock
    )
    monkeypatch.setattr("app.api.v1.endpoints.blueprints.crud_event", crud_event_mock)


def test_instantiate_blueprint_success(monkeypatch, test_client: TestClient):
    """
    Tests creating a new event from a blueprint.
    """
    apply_mocks(monkeypatch)

    # Simulate finding the blueprint in the database
    mock_blueprint = MagicMock()
    mock_blueprint.organization_id = "org_abc"
    mock_blueprint.template = {"description": "Blueprint Description"}
    crud_blueprint_mock.blueprint.get.return_value = mock_blueprint

    # Simulate the event creation
    return_event = EventSchema(
        id="evt_new",
        organization_id="org_abc",
        name="New Event from Blueprint",
        version=1,
        status=EventStatus.draft,
        start_date=datetime.now(timezone.utc),
        end_date=datetime.now(timezone.utc),
        is_public=False,
    )
    crud_event_mock.event.create_with_organization.return_value = return_event

    request_body = {
        "name": "New Event from Blueprint",
        "start_date": "2025-12-01T10:00:00Z",
        "end_date": "2025-12-01T18:00:00Z",
    }

    response = test_client.post(
        "/api/v1/organizations/org_abc/blueprints/bp_1/instantiate", json=request_body
    )

    assert response.status_code == 201
    assert response.json()["name"] == "New Event from Blueprint"

    # Check that the create function was called with data combined from the blueprint and the request
    created_event_data = (
        crud_event_mock.event.create_with_organization.call_args.kwargs["obj_in"]
    )
    assert created_event_data.description == "Blueprint Description"
    assert created_event_data.name == "New Event from Blueprint"
