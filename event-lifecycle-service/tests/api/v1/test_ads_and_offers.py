# tests/api/v1/test_ads_and_offers.py

from fastapi.testclient import TestClient
from unittest.mock import MagicMock


from app.schemas.ad import Ad as AdSchema
from app.schemas.offer import Offer as OfferSchema

crud_ad_mock = MagicMock()
crud_offer_mock = MagicMock()


class MockTokenPayload:
    def __init__(self, sub, org_id):
        self.sub = sub
        self.org_id = org_id


def override_get_current_user():
    return MockTokenPayload(sub="user_123", org_id="org_abc")


# --- Ad Tests ---
def test_create_ad_success(monkeypatch, test_client: TestClient):
    monkeypatch.setattr("app.api.v1.endpoints.ads.crud_ad", crud_ad_mock)

    ad_data = {
        "name": "Q3 Banner Ad",
        "event_id": "evt_1",
        "content_type": "BANNER",
        "media_url": "http://example.com/img.png",
        "click_url": "http://example.com",
    }
    return_ad = AdSchema(
        id="ad_1", organization_id="org_abc", is_archived=False, **ad_data
    )
    crud_ad_mock.ad.create_with_organization.return_value = return_ad

    response = test_client.post("/api/v1/organizations/org_abc/ads", json=ad_data)

    assert response.status_code == 201
    assert response.json()["name"] == "Q3 Banner Ad"


# --- Offer Tests ---
def test_create_offer_success(monkeypatch, test_client: TestClient):
    monkeypatch.setattr("app.api.v1.endpoints.offers.crud_offer", crud_offer_mock)

    offer_data = {
        "event_id": "evt_1",
        "title": "VIP Upgrade",
        "price": 50.0,
        "offer_type": "TICKET_UPGRADE",
        "expires_at": "2025-10-10T10:00:00Z",
    }
    return_offer = OfferSchema(
        id="offer_1", organization_id="org_abc", is_archived=False, **offer_data
    )
    crud_offer_mock.offer.create_with_organization.return_value = return_offer

    response = test_client.post("/api/v1/organizations/org_abc/offers", json=offer_data)

    assert response.status_code == 201
    assert response.json()["title"] == "VIP Upgrade"
