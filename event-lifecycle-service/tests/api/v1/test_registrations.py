# tests/api/v1/test_registrations.py

from fastapi.testclient import TestClient
from unittest.mock import MagicMock

from app.schemas.registration import (
    Registration as RegistrationSchema,
    RegistrationStatus,
)

crud_registration_mock = MagicMock()
crud_event_mock = MagicMock()


class MockTokenPayload:
    def __init__(self, sub, org_id):
        self.sub = sub
        self.org_id = org_id


def override_get_current_user():
    return MockTokenPayload(sub="user_123", org_id="org_abc")


def test_create_registration_conflict(monkeypatch, test_client: TestClient):
    monkeypatch.setattr(
        "app.api.v1.endpoints.registrations.crud_registration", crud_registration_mock
    )
    monkeypatch.setattr(
        "app.api.v1.endpoints.registrations.crud_event", crud_event_mock
    )

    mock_event = MagicMock(organization_id="org_abc")
    crud_event_mock.event.get.return_value = mock_event

    crud_registration_mock.registration.get_by_user_or_email.return_value = {
        "id": "reg_existing"
    }

    request_body = {"user_id": "user_123"}
    response = test_client.post(
        "/api/v1/organizations/org_abc/events/evt_1/registrations", json=request_body
    )

    assert response.status_code == 409
    assert "already registered" in response.json()["detail"]


def test_create_registration_success(monkeypatch, test_client: TestClient):
    monkeypatch.setattr(
        "app.api.v1.endpoints.registrations.crud_registration", crud_registration_mock
    )
    monkeypatch.setattr(
        "app.api.v1.endpoints.registrations.crud_event", crud_event_mock
    )

    mock_event = MagicMock(organization_id="org_abc")
    crud_event_mock.event.get.return_value = mock_event

    crud_registration_mock.registration.get_by_user_or_email.return_value = None

    return_reg = RegistrationSchema(
        id="reg_new",
        event_id="evt_1",
        status=RegistrationStatus.confirmed,
        ticket_code="ABC-123",
        user_id="user_123",
    )
    crud_registration_mock.registration.create_for_event.return_value = return_reg

    request_body = {"user_id": "user_123"}
    response = test_client.post(
        "/api/v1/organizations/org_abc/events/evt_1/registrations", json=request_body
    )

    assert response.status_code == 201
    assert response.json()["id"] == "reg_new"
