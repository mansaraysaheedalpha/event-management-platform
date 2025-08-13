# tests/api/v1/test_sessions.py

from fastapi.testclient import TestClient
from unittest.mock import MagicMock
from datetime import datetime, timezone

from app.schemas.session import Session as SessionSchema

crud_session_mock = MagicMock()
crud_event_mock = MagicMock()


class MockTokenPayload:
    def __init__(self, sub, org_id):
        self.sub = sub
        self.org_id = org_id


def override_get_current_user():
    return MockTokenPayload(sub="user_123", org_id="org_abc")

# Helper function to apply mocks
def apply_mocks(monkeypatch):
    monkeypatch.setattr("app.api.v1.endpoints.sessions.crud_session", crud_session_mock)
    monkeypatch.setattr("app.api.v1.endpoints.sessions.crud_event", crud_event_mock)


# --- CREATE ---
def test_create_session_success(monkeypatch, test_client: TestClient):
    apply_mocks(monkeypatch)
    mock_event = MagicMock(organization_id="org_abc")
    crud_event_mock.event.get.return_value = mock_event
    request_body = {
        "title": "My Session",
        "start_time": "2025-11-10T10:00:00Z",
        "end_time": "2025-11-10T11:00:00Z",
    }
    return_session = SessionSchema(
        id="session_1", event_id="evt_1", speakers=[], **request_body
    )
    crud_session_mock.session.create_with_event.return_value = return_session
    response = test_client.post(
        "/api/v1/organizations/org_abc/events/evt_1/sessions", json=request_body
    )
    assert response.status_code == 201
    assert response.json()["title"] == "My Session"


def test_create_session_forbidden(monkeypatch, test_client: TestClient):
    apply_mocks(monkeypatch)
    request_body = {
        "title": "My Session",
        "start_time": "2025-11-10T10:00:00Z",
        "end_time": "2025-11-10T11:00:00Z",
    }
    response = test_client.post(
        "/api/v1/organizations/org_xyz/events/evt_1/sessions", json=request_body
    )
    assert response.status_code == 403


# --- READ ---
def test_list_sessions_success(monkeypatch, test_client: TestClient):
    apply_mocks(monkeypatch)
    return_sessions = [
        SessionSchema(
            id="s1",
            event_id="e1",
            title="S1",
            start_time=datetime.now(timezone.utc),
            end_time=datetime.now(timezone.utc),
        ),
        SessionSchema(
            id="s2",
            event_id="e1",
            title="S2",
            start_time=datetime.now(timezone.utc),
            end_time=datetime.now(timezone.utc),
        ),
    ]
    crud_session_mock.session.get_multi_by_event.return_value = return_sessions
    response = test_client.get("/api/v1/organizations/org_abc/events/evt_1/sessions")
    assert response.status_code == 200
    assert len(response.json()) == 2


def test_get_session_not_found(monkeypatch, test_client: TestClient):
    apply_mocks(monkeypatch)
    crud_session_mock.session.get.return_value = None
    response = test_client.get(
        "/api/v1/organizations/org_abc/events/evt_1/sessions/s_nonexistent"
    )
    assert response.status_code == 404


# --- UPDATE ---
def test_update_session_success(monkeypatch, test_client: TestClient):
    apply_mocks(monkeypatch)
    mock_session = MagicMock()
    crud_session_mock.session.get.return_value = mock_session
    updated_session = SessionSchema(
        id="s1",
        event_id="e1",
        title="Updated",
        start_time=datetime.now(timezone.utc),
        end_time=datetime.now(timezone.utc),
    )
    crud_session_mock.session.update.return_value = updated_session
    response = test_client.patch(
        "/api/v1/organizations/org_abc/events/evt_1/sessions/s1",
        json={"title": "Updated"},
    )
    assert response.status_code == 200
    assert response.json()["title"] == "Updated"


# --- DELETE ---
def test_delete_session_success(monkeypatch, test_client: TestClient):
    apply_mocks(monkeypatch)
    mock_session = MagicMock()
    crud_session_mock.session.get.return_value = mock_session
    response = test_client.delete("/api/v1/organizations/org_abc/events/evt_1/sessions/s1")
    assert response.status_code == 204
