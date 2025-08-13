from fastapi.testclient import TestClient
from unittest.mock import MagicMock, patch

from app.main import app

# Mocks
crud_session_mock = MagicMock()


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
        "app.api.v1.endpoints.presentations.crud_session", crud_session_mock
    )
    crud_session_mock.session.get.return_value = {"id": "session_1"}

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
        "app.api.v1.endpoints.presentations.crud_session", crud_session_mock
    )
    crud_session_mock.session.get.return_value = {"id": "session_1"}

    s3_key = "uploads/presentations/session_1/test.pdf"
    request_body = {"s3_key": s3_key}

    response = test_client.post(
        "/api/v1/organizations/org_abc/events/evt_1/sessions/session_1/presentation/process",
        json=request_body,
    )

    assert response.status_code == 202
    assert response.json() == {"message": "Presentation processing has been initiated."}

    # Assert that the Celery task was called with the correct S3 key
    mock_celery_delay.assert_called_once_with(session_id="session_1", s3_key=s3_key)
