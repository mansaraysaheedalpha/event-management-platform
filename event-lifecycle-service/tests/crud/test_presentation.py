from fastapi.testclient import TestClient
from unittest.mock import MagicMock, patch

from app.main import app

# Mocks
crud_event_mock = MagicMock()
crud_session_mock = MagicMock()
crud_presentation_mock = MagicMock()


class MockEvent:
    def __init__(self, id, organization_id):
        self.id = id
        self.organization_id = organization_id


class MockSession:
    def __init__(self, id, event_id):
        self.id = id
        self.event_id = event_id


class MockPresentation:
    def __init__(self, id, session_id, slide_urls):
        self.id = id
        self.session_id = session_id
        self.slide_urls = slide_urls

    def model_dump(self):  # Simulate Pydantic v2 model_dump for response validation
        return {
            "id": self.id,
            "session_id": self.session_id,
            "slide_urls": self.slide_urls,
            "model_config": {"from_attributes": True},
        }


class MockTokenPayload:
    def __init__(self, sub, org_id):
        self.sub = sub
        self.org_id = org_id


def override_get_current_user():
    return MockTokenPayload(sub="user_123", org_id="org_abc")


@patch("app.api.v1.endpoints.presentations.generate_presigned_post")
def test_request_presentation_upload(
    mock_generate_presigned, monkeypatch, test_client: TestClient
):
    """
    Tests that the upload-request endpoint returns a pre-signed S3 URL.
    """
    monkeypatch.setattr(
        "app.api.v1.endpoints.presentations.crud_event", crud_event_mock
    )
    monkeypatch.setattr(
        "app.api.v1.endpoints.presentations.crud_session", crud_session_mock
    )
    crud_event_mock.event.get.return_value = MockEvent(
        id="evt_1", organization_id="org_abc"
    )
    crud_session_mock.session.get.return_value = MockSession(
        id="session_1", event_id="evt_1"
    )

    # Simulate the return value from the S3 helper
    presigned_data = {"url": "https://s3...", "fields": {"key": "value"}}
    mock_generate_presigned.return_value = presigned_data

    request_body = {"filename": "test.pdf", "content_type": "application/pdf"}
    response = test_client.post(
        "/api/v1/organizations/org_abc/events/evt_1/sessions/session_1/presentation/upload-request",
        json=request_body,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["url"] == presigned_data["url"]
    assert "s3_key" in data
    mock_generate_presigned.assert_called_once()


@patch("app.api.v1.endpoints.presentations.process_presentation.delay")
def test_process_uploaded_presentation(
    mock_celery_delay, monkeypatch, test_client: TestClient
):
    """
    Tests that the process endpoint successfully dispatches a Celery task.
    """
    monkeypatch.setattr(
        "app.api.v1.endpoints.presentations.crud_event", crud_event_mock
    )
    monkeypatch.setattr(
        "app.api.v1.endpoints.presentations.crud_session", crud_session_mock
    )
    crud_event_mock.event.get.return_value = MockEvent(
        id="evt_1", organization_id="org_abc"
    )
    crud_session_mock.session.get.return_value = MockSession(
        id="session_1", event_id="evt_1"
    )

    s3_key = "uploads/presentations/session_1/test.pdf"
    request_body = {"s3_key": s3_key}

    response = test_client.post(
        "/api/v1/organizations/org_abc/events/evt_1/sessions/session_1/presentation/process",
        json=request_body,
    )

    assert response.status_code == 202
    assert response.json() == {"message": "Presentation processing has been initiated."}
    mock_celery_delay.assert_called_once_with(session_id="session_1", s3_key=s3_key)


def test_get_presentation_by_session_success(monkeypatch, test_client: TestClient):
    """
    Tests successfully retrieving a presentation for a session.
    """
    monkeypatch.setattr(
        "app.api.v1.endpoints.presentations.crud_event", crud_event_mock
    )
    monkeypatch.setattr(
        "app.api.v1.endpoints.presentations.crud_session", crud_session_mock
    )
    monkeypatch.setattr(
        "app.api.v1.endpoints.presentations.crud_presentation", crud_presentation_mock
    )

    crud_event_mock.event.get.return_value = MockEvent(
        id="evt_1", organization_id="org_abc"
    )
    crud_session_mock.session.get.return_value = MockSession(
        id="session_1", event_id="evt_1"
    )
    mock_presentation = MockPresentation(
        id="pres_1", session_id="session_1", slide_urls=["url1", "url2"]
    )
    crud_presentation_mock.presentation.get_by_session.return_value = mock_presentation

    response = test_client.get(
        "/api/v1/organizations/org_abc/events/evt_1/sessions/session_1/presentation"
    )

    assert response.status_code == 200
    # Pydantic v1 would use .dict(), v2 uses .model_dump_json() or similar
    # For a test, comparing the dict representation is sufficient.
    assert response.json()["id"] == mock_presentation.id
    assert response.json()["slide_urls"] == mock_presentation.slide_urls


def test_get_presentation_by_session_not_found(monkeypatch, test_client: TestClient):
    """
    Tests that a 404 is returned when a presentation is not found for a session.
    """
    monkeypatch.setattr(
        "app.api.v1.endpoints.presentations.crud_event", crud_event_mock
    )
    monkeypatch.setattr(
        "app.api.v1.endpoints.presentations.crud_session", crud_session_mock
    )
    monkeypatch.setattr(
        "app.api.v1.endpoints.presentations.crud_presentation", crud_presentation_mock
    )

    crud_event_mock.event.get.return_value = MockEvent(
        id="evt_1", organization_id="org_abc"
    )
    crud_session_mock.session.get.return_value = MockSession(
        id="session_1", event_id="evt_1"
    )
    crud_presentation_mock.presentation.get_by_session.return_value = None  # Not found

    response = test_client.get(
        "/api/v1/organizations/org_abc/events/evt_1/sessions/session_1/presentation"
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "Presentation not found"}
