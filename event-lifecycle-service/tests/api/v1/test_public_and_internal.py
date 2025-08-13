from fastapi.testclient import TestClient
from unittest.mock import MagicMock
from datetime import datetime, timezone
from app.core.config import settings
from app.schemas.event import Event as EventSchema, EventStatus


crud_event_mock = MagicMock()
crud_ad_mock = MagicMock()


def test_get_public_event_success(monkeypatch, test_client: TestClient):
    monkeypatch.setattr("app.api.v1.endpoints.public.crud_event", crud_event_mock)

    mock_event = EventSchema(
        id="evt_1",
        name="Public Event",
        organization_id="org_abc",
        version=1,
        status=EventStatus.published,
        start_date=datetime.now(timezone.utc),
        end_date=datetime.now(timezone.utc),
        is_public=True,
        is_archived=False,
        createdAt=datetime.now(timezone.utc),
        updatedAt=datetime.now(timezone.utc),
    )
    crud_event_mock.event.get.return_value = mock_event

    response = test_client.get("/api/v1/public/events/evt_1")
    assert response.status_code == 200
    assert response.json()["name"] == "Public Event"


def test_get_public_event_not_found(monkeypatch, test_client: TestClient):
    monkeypatch.setattr("app.api.v1.endpoints.public.crud_event", crud_event_mock)

    # For this test, a MagicMock is fine because the code only checks boolean flags
    mock_event = MagicMock(is_archived=False, is_public=False)
    crud_event_mock.event.get.return_value = mock_event

    response = test_client.get("/api/v1/public/events/evt_1")
    assert response.status_code == 404


def test_get_internal_ad_success(monkeypatch, test_client: TestClient):
    monkeypatch.setattr("app.api.v1.endpoints.internals.crud_ad", crud_ad_mock)

    mock_ad_from_db = MagicMock(
        id="ad_1",
        event_id="evt_1",
        content_type="IMAGE",
        media_url="http://a.com/img.png",
        click_url="http://a.com",
        is_archived=False,
    )
    crud_ad_mock.ad.get.return_value = mock_ad_from_db

    headers = {"X-Internal-Api-Key": settings.INTERNAL_API_KEY}
    response = test_client.get("/api/v1/internal/ads/ad_1", headers=headers)

    assert response.status_code == 200
    assert response.json()["media_url"] == "http://a.com/img.png"


def test_get_internal_ad_forbidden(monkeypatch, test_client: TestClient):
    monkeypatch.setattr("app.api.v1.endpoints.internals.crud_ad", crud_ad_mock)

    headers = {"X-Internal-Api-Key": "invalid-key"}
    response = test_client.get("/api/v1/internal/ads/ad_1", headers=headers)

    assert response.status_code == 401
