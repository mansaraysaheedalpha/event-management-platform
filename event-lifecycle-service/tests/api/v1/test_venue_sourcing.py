# tests/api/v1/test_venue_sourcing.py
"""
Comprehensive integration tests for venue sourcing endpoints:
  - Venue Admin (approve / reject / suspend / request-docs / verification)
  - Venue Directory (search, detail, amenities, countries, cities)
  - Venue Spaces (CRUD + pricing, auth boundary)
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

# Patch the DB engine before importing app so lifespan doesn't hit real DB
with patch("app.db.session.engine") as _mock_engine:
    _mock_engine.connect.return_value = MagicMock()
    from app.api import deps
    from app.db.session import get_db
    from app.main import app


@pytest.fixture()
def test_client():
    """Self-contained test client that mocks DB, auth, and Kafka."""
    from app.core.kafka_producer import get_kafka_producer

    app.dependency_overrides[get_db] = lambda: MagicMock()
    app.dependency_overrides[deps.get_current_user] = lambda: MockTokenPayload()
    app.dependency_overrides[get_kafka_producer] = lambda: (yield MagicMock())

    # Patch lifespan DB and scheduler calls so TestClient can start without infra
    with patch("app.main.Base.metadata.create_all"), \
         patch("app.scheduler.init_scheduler"), \
         patch("app.scheduler.shutdown_scheduler"), \
         patch("app.db.redis.redis_client", MagicMock()):
        with TestClient(app) as client:
            yield client

    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Mock helpers
# ---------------------------------------------------------------------------

class MockTokenPayload:
    """Lightweight stand-in for app.schemas.token.TokenPayload."""

    def __init__(self, sub="user_123", org_id="org_abc", role=None):
        self.sub = sub
        self.org_id = org_id
        self.role = role


def _admin_override():
    return MockTokenPayload(sub="admin_1", org_id="org_abc", role="admin")


def _superadmin_override():
    return MockTokenPayload(sub="admin_2", org_id="org_abc", role="superadmin")


def _attendee_override():
    return MockTokenPayload(sub="user_1", org_id="org_abc", role="attendee")


def _no_role_override():
    return MockTokenPayload(sub="user_2", org_id="org_abc", role=None)


def _other_org_override():
    return MockTokenPayload(sub="user_3", org_id="org_other", role=None)


def _make_mock_venue(**overrides):
    """Return a MagicMock that behaves like a Venue ORM object."""
    defaults = dict(
        id="venue_1",
        slug="test-venue",
        name="Test Venue",
        description="A test venue",
        address="123 Main St",
        city="Nairobi",
        country="Kenya",
        latitude=-1.286,
        longitude=36.817,
        website="https://testvenue.com",
        phone="+254700000000",
        email="venue@example.com",
        whatsapp=None,
        total_capacity=500,
        verified=True,
        status="approved",
        approved_at=datetime.now(timezone.utc),
        rejection_reason=None,
        organization_id="org_abc",
        is_archived=False,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        photos=[],
        spaces=[],
        venue_amenities=[],
    )
    defaults.update(overrides)
    venue = MagicMock()
    for k, v in defaults.items():
        setattr(venue, k, v)
    return venue


# ---------------------------------------------------------------------------
# A. Admin auth boundary tests
# ---------------------------------------------------------------------------

class TestAdminAuthBoundary:
    """Non-admin users must receive 403 on all admin endpoints."""

    ADMIN_URLS = [
        ("GET", "/api/v1/admin/venues"),
        ("POST", "/api/v1/admin/venues/venue_1/approve"),
        ("POST", "/api/v1/admin/venues/venue_1/reject"),
        ("POST", "/api/v1/admin/venues/venue_1/suspend"),
        ("POST", "/api/v1/admin/venues/venue_1/request-documents"),
        ("GET", "/api/v1/admin/venues/venue_1"),
        ("PATCH", "/api/v1/admin/venues/venue_1/verification/doc_1"),
    ]

    # Bodies required by endpoints that validate request body
    BODIES = {
        "/api/v1/admin/venues/venue_1/reject": {"reason": "bad"},
        "/api/v1/admin/venues/venue_1/suspend": {"reason": "policy"},
        "/api/v1/admin/venues/venue_1/request-documents": {"message": "send docs"},
        "/api/v1/admin/venues/venue_1/verification/doc_1": {"status": "accepted"},
    }

    def test_attendee_role_gets_403(self, test_client: TestClient):
        """A user with role='attendee' must be rejected from admin endpoints."""
        app.dependency_overrides[deps.get_current_user] = _attendee_override
        try:
            for method, url in self.ADMIN_URLS:
                body = self.BODIES.get(url)
                if method == "GET":
                    resp = test_client.get(url)
                elif method == "POST":
                    resp = test_client.post(url, json=body or {})
                else:
                    resp = test_client.patch(url, json=body or {})
                assert resp.status_code == 403, f"{method} {url} returned {resp.status_code}"
        finally:
            app.dependency_overrides[deps.get_current_user] = lambda: MockTokenPayload()

    def test_no_role_gets_403(self, test_client: TestClient):
        """A user with role=None must be rejected from admin endpoints."""
        app.dependency_overrides[deps.get_current_user] = _no_role_override
        try:
            resp = test_client.get("/api/v1/admin/venues")
            assert resp.status_code == 403
        finally:
            app.dependency_overrides[deps.get_current_user] = lambda: MockTokenPayload()

    def test_admin_can_access(self, monkeypatch, test_client: TestClient):
        """Admin user can hit the list-venues endpoint successfully."""
        mock_crud = MagicMock()
        mock_crud.get_admin_venues.return_value = {"venues": [], "total": 0}
        monkeypatch.setattr(
            "app.api.v1.endpoints.venue_admin.crud_venue_obj", mock_crud
        )
        app.dependency_overrides[deps.get_current_user] = _admin_override
        try:
            resp = test_client.get("/api/v1/admin/venues")
            assert resp.status_code == 200
        finally:
            app.dependency_overrides[deps.get_current_user] = lambda: MockTokenPayload()

    def test_superadmin_can_access(self, monkeypatch, test_client: TestClient):
        """Superadmin role should also be accepted."""
        mock_crud = MagicMock()
        mock_crud.get_admin_venues.return_value = {"venues": [], "total": 0}
        monkeypatch.setattr(
            "app.api.v1.endpoints.venue_admin.crud_venue_obj", mock_crud
        )
        app.dependency_overrides[deps.get_current_user] = _superadmin_override
        try:
            resp = test_client.get("/api/v1/admin/venues")
            assert resp.status_code == 200
        finally:
            app.dependency_overrides[deps.get_current_user] = lambda: MockTokenPayload()


# ---------------------------------------------------------------------------
# B. State machine tests (approve / reject / suspend)
# ---------------------------------------------------------------------------

class TestStateMachine:
    """The venue CRUD layer raises ValueError for invalid state transitions.
    The endpoint converts these to HTTP 422."""

    def _setup_admin(self):
        app.dependency_overrides[deps.get_current_user] = _admin_override

    def _teardown_admin(self):
        app.dependency_overrides[deps.get_current_user] = lambda: MockTokenPayload()

    # -- Approve --

    def test_approve_not_pending_review_returns_422(
        self, monkeypatch, test_client: TestClient
    ):
        mock_crud = MagicMock()
        mock_crud.approve.side_effect = ValueError(
            "Can only approve venues in pending_review status"
        )
        monkeypatch.setattr(
            "app.api.v1.endpoints.venue_admin.crud_venue_obj", mock_crud
        )
        self._setup_admin()
        try:
            resp = test_client.post("/api/v1/admin/venues/venue_1/approve")
            assert resp.status_code == 422
            assert "pending_review" in resp.json()["detail"]
        finally:
            self._teardown_admin()

    def test_approve_happy_path(self, monkeypatch, test_client: TestClient):
        venue = _make_mock_venue(status="approved", verified=True)
        mock_crud = MagicMock()
        mock_crud.approve.return_value = venue
        monkeypatch.setattr(
            "app.api.v1.endpoints.venue_admin.crud_venue_obj", mock_crud
        )
        self._setup_admin()
        try:
            resp = test_client.post("/api/v1/admin/venues/venue_1/approve")
            assert resp.status_code == 200
            data = resp.json()
            assert data["id"] == "venue_1"
            assert data["status"] == "approved"
            assert data["verified"] is True
        finally:
            self._teardown_admin()

    # -- Reject --

    def test_reject_not_pending_review_returns_422(
        self, monkeypatch, test_client: TestClient
    ):
        mock_crud = MagicMock()
        mock_crud.reject.side_effect = ValueError(
            "Can only reject venues in pending_review status"
        )
        monkeypatch.setattr(
            "app.api.v1.endpoints.venue_admin.crud_venue_obj", mock_crud
        )
        self._setup_admin()
        try:
            resp = test_client.post(
                "/api/v1/admin/venues/venue_1/reject",
                json={"reason": "Missing information"},
            )
            assert resp.status_code == 422
            assert "pending_review" in resp.json()["detail"]
        finally:
            self._teardown_admin()

    def test_reject_happy_path(self, monkeypatch, test_client: TestClient):
        venue = _make_mock_venue(
            status="rejected", rejection_reason="Incomplete docs"
        )
        mock_crud = MagicMock()
        mock_crud.reject.return_value = venue
        monkeypatch.setattr(
            "app.api.v1.endpoints.venue_admin.crud_venue_obj", mock_crud
        )
        self._setup_admin()
        try:
            resp = test_client.post(
                "/api/v1/admin/venues/venue_1/reject",
                json={"reason": "Incomplete docs"},
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["status"] == "rejected"
            assert data["rejection_reason"] == "Incomplete docs"
        finally:
            self._teardown_admin()

    # -- Suspend --

    def test_suspend_not_approved_returns_422(
        self, monkeypatch, test_client: TestClient
    ):
        mock_crud = MagicMock()
        mock_crud.suspend.side_effect = ValueError(
            "Can only suspend venues in approved status"
        )
        monkeypatch.setattr(
            "app.api.v1.endpoints.venue_admin.crud_venue_obj", mock_crud
        )
        self._setup_admin()
        try:
            resp = test_client.post(
                "/api/v1/admin/venues/venue_1/suspend",
                json={"reason": "Policy violation"},
            )
            assert resp.status_code == 422
            assert "approved" in resp.json()["detail"]
        finally:
            self._teardown_admin()

    def test_suspend_happy_path(self, monkeypatch, test_client: TestClient):
        venue = _make_mock_venue(status="suspended")
        mock_crud = MagicMock()
        mock_crud.suspend.return_value = venue
        monkeypatch.setattr(
            "app.api.v1.endpoints.venue_admin.crud_venue_obj", mock_crud
        )
        self._setup_admin()
        try:
            resp = test_client.post(
                "/api/v1/admin/venues/venue_1/suspend",
                json={"reason": "Policy violation"},
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["status"] == "suspended"
        finally:
            self._teardown_admin()

    # -- Approve venue not found --

    def test_approve_venue_not_found_returns_404(
        self, monkeypatch, test_client: TestClient
    ):
        mock_crud = MagicMock()
        mock_crud.approve.return_value = None
        monkeypatch.setattr(
            "app.api.v1.endpoints.venue_admin.crud_venue_obj", mock_crud
        )
        self._setup_admin()
        try:
            resp = test_client.post("/api/v1/admin/venues/nonexistent/approve")
            assert resp.status_code == 404
        finally:
            self._teardown_admin()


# ---------------------------------------------------------------------------
# C. Directory tests (public endpoints)
# ---------------------------------------------------------------------------

class TestVenueDirectory:
    """Public venue directory search and detail endpoints."""

    def test_search_returns_results(self, monkeypatch, test_client: TestClient):
        mock_crud = MagicMock()
        mock_crud.search_directory.return_value = {
            "venues": [
                {
                    "id": "v1",
                    "slug": "grand-hall",
                    "name": "Grand Hall",
                    "city": "Nairobi",
                    "country": "Kenya",
                    "address": "1 Main St",
                    "latitude": -1.3,
                    "longitude": 36.8,
                    "total_capacity": 200,
                    "verified": True,
                    "cover_photo_url": None,
                    "space_count": 2,
                    "min_price": None,
                    "amenity_highlights": ["WiFi", "Projector"],
                    "created_at": datetime.now(timezone.utc).isoformat(),
                }
            ],
            "pagination": {
                "page": 1,
                "page_size": 12,
                "total_count": 1,
                "total_pages": 1,
            },
        }
        monkeypatch.setattr(
            "app.api.v1.endpoints.venue_directory.crud_venue_obj", mock_crud
        )
        resp = test_client.get("/api/v1/venues/directory?q=grand")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["venues"]) == 1
        assert data["venues"][0]["name"] == "Grand Hall"
        assert data["pagination"]["total_count"] == 1

    def test_search_empty(self, monkeypatch, test_client: TestClient):
        mock_crud = MagicMock()
        mock_crud.search_directory.return_value = {
            "venues": [],
            "pagination": {
                "page": 1,
                "page_size": 12,
                "total_count": 0,
                "total_pages": 0,
            },
        }
        monkeypatch.setattr(
            "app.api.v1.endpoints.venue_directory.crud_venue_obj", mock_crud
        )
        resp = test_client.get("/api/v1/venues/directory?q=nonexistent")
        assert resp.status_code == 200
        assert resp.json()["venues"] == []

    def test_venue_detail_by_slug_found(self, monkeypatch, test_client: TestClient):
        venue = _make_mock_venue(slug="grand-hall")
        mock_crud = MagicMock()
        mock_crud.get_by_slug.return_value = venue
        monkeypatch.setattr(
            "app.api.v1.endpoints.venue_directory.crud_venue_obj", mock_crud
        )
        monkeypatch.setattr(
            "app.api.v1.endpoints.venue_directory._resolve_org_name",
            lambda org_id: "Test Organization",
        )
        resp = test_client.get("/api/v1/venues/directory/grand-hall")
        assert resp.status_code == 200
        data = resp.json()
        assert data["slug"] == "grand-hall"
        assert data["name"] == "Test Venue"
        assert data["listed_by"]["name"] == "Test Organization"

    def test_venue_detail_by_slug_not_found(
        self, monkeypatch, test_client: TestClient
    ):
        mock_crud = MagicMock()
        mock_crud.get_by_slug.return_value = None
        monkeypatch.setattr(
            "app.api.v1.endpoints.venue_directory.crud_venue_obj", mock_crud
        )
        resp = test_client.get("/api/v1/venues/directory/no-such-venue")
        assert resp.status_code == 404

    def test_amenity_categories(self, monkeypatch, test_client: TestClient):
        mock_amenity_crud = MagicMock()
        mock_amenity_crud.get_all_categories.return_value = []
        monkeypatch.setattr(
            "app.api.v1.endpoints.venue_directory.crud_amenity_obj",
            mock_amenity_crud,
        )
        # Ensure cache miss
        monkeypatch.setattr(
            "app.api.v1.endpoints.venue_directory._cache_get", lambda key: None
        )
        monkeypatch.setattr(
            "app.api.v1.endpoints.venue_directory._cache_set", lambda *a, **kw: None
        )
        resp = test_client.get("/api/v1/venues/amenities")
        assert resp.status_code == 200
        assert "categories" in resp.json()

    def test_countries_list(self, monkeypatch, test_client: TestClient):
        mock_crud = MagicMock()
        mock_crud.get_countries_with_venues.return_value = [
            {"country": "Kenya", "venue_count": 5}
        ]
        monkeypatch.setattr(
            "app.api.v1.endpoints.venue_directory.crud_venue_obj", mock_crud
        )
        monkeypatch.setattr(
            "app.api.v1.endpoints.venue_directory._cache_get", lambda key: None
        )
        monkeypatch.setattr(
            "app.api.v1.endpoints.venue_directory._cache_set", lambda *a, **kw: None
        )
        resp = test_client.get("/api/v1/venues/countries")
        assert resp.status_code == 200
        data = resp.json()
        assert data["countries"][0]["country"] == "Kenya"

    def test_cities_list(self, monkeypatch, test_client: TestClient):
        mock_crud = MagicMock()
        mock_crud.get_cities_with_venues.return_value = [
            {"city": "Nairobi", "country": "Kenya", "venue_count": 3}
        ]
        monkeypatch.setattr(
            "app.api.v1.endpoints.venue_directory.crud_venue_obj", mock_crud
        )
        monkeypatch.setattr(
            "app.api.v1.endpoints.venue_directory._cache_get", lambda key: None
        )
        monkeypatch.setattr(
            "app.api.v1.endpoints.venue_directory._cache_set", lambda *a, **kw: None
        )
        resp = test_client.get("/api/v1/venues/cities?country=Kenya")
        assert resp.status_code == 200
        data = resp.json()
        assert data["cities"][0]["city"] == "Nairobi"


# ---------------------------------------------------------------------------
# D. Schema validation tests
# ---------------------------------------------------------------------------

class TestSchemaValidation:
    """Pydantic schema validation produces 422 on invalid payloads."""

    def _setup_admin(self):
        app.dependency_overrides[deps.get_current_user] = _admin_override

    def _teardown_admin(self):
        app.dependency_overrides[deps.get_current_user] = lambda: MockTokenPayload()

    # -- Pricing validation --

    def test_pricing_invalid_rate_type(self, monkeypatch, test_client: TestClient):
        """rate_type must be one of hourly, half_day, full_day."""
        mock_crud = MagicMock()
        mock_venue = _make_mock_venue()
        mock_crud.get.return_value = mock_venue
        monkeypatch.setattr(
            "app.api.v1.endpoints.venue_spaces.crud_venue_obj", mock_crud
        )
        resp = test_client.put(
            "/api/v1/organizations/org_abc/venues/venue_1/spaces/space_1/pricing",
            json={"pricing": [{"rate_type": "weekly", "amount": 100, "currency": "USD"}]},
        )
        assert resp.status_code == 422

    def test_pricing_amount_zero(self, monkeypatch, test_client: TestClient):
        """amount must be > 0."""
        mock_crud = MagicMock()
        mock_venue = _make_mock_venue()
        mock_crud.get.return_value = mock_venue
        monkeypatch.setattr(
            "app.api.v1.endpoints.venue_spaces.crud_venue_obj", mock_crud
        )
        resp = test_client.put(
            "/api/v1/organizations/org_abc/venues/venue_1/spaces/space_1/pricing",
            json={"pricing": [{"rate_type": "hourly", "amount": 0, "currency": "USD"}]},
        )
        assert resp.status_code == 422

    def test_pricing_negative_amount(self, monkeypatch, test_client: TestClient):
        """amount must be > 0 (negative check)."""
        resp = test_client.put(
            "/api/v1/organizations/org_abc/venues/venue_1/spaces/space_1/pricing",
            json={"pricing": [{"rate_type": "hourly", "amount": -50, "currency": "USD"}]},
        )
        assert resp.status_code == 422

    def test_pricing_bad_currency_too_short(self, test_client: TestClient):
        """currency must be exactly 3 characters."""
        resp = test_client.put(
            "/api/v1/organizations/org_abc/venues/venue_1/spaces/space_1/pricing",
            json={"pricing": [{"rate_type": "hourly", "amount": 100, "currency": "US"}]},
        )
        assert resp.status_code == 422

    def test_pricing_bad_currency_too_long(self, test_client: TestClient):
        """currency must be exactly 3 characters."""
        resp = test_client.put(
            "/api/v1/organizations/org_abc/venues/venue_1/spaces/space_1/pricing",
            json={"pricing": [{"rate_type": "hourly", "amount": 100, "currency": "USDD"}]},
        )
        assert resp.status_code == 422

    # -- Admin reject reason --

    def test_reject_empty_reason(self, test_client: TestClient):
        """AdminRejectRequest.reason must have min_length=1."""
        self._setup_admin()
        try:
            resp = test_client.post(
                "/api/v1/admin/venues/venue_1/reject",
                json={"reason": ""},
            )
            assert resp.status_code == 422
        finally:
            self._teardown_admin()

    # -- Admin suspend reason --

    def test_suspend_empty_reason(self, test_client: TestClient):
        """AdminSuspendRequest.reason must have min_length=1."""
        self._setup_admin()
        try:
            resp = test_client.post(
                "/api/v1/admin/venues/venue_1/suspend",
                json={"reason": ""},
            )
            assert resp.status_code == 422
        finally:
            self._teardown_admin()

    # -- Verification status --

    def test_verification_status_invalid_value(self, test_client: TestClient):
        """AdminVerificationStatusUpdate.status must match ^(accepted|rejected)$."""
        self._setup_admin()
        try:
            resp = test_client.patch(
                "/api/v1/admin/venues/venue_1/verification/doc_1",
                json={"status": "pending"},
            )
            assert resp.status_code == 422
        finally:
            self._teardown_admin()

    def test_verification_status_missing(self, test_client: TestClient):
        """status is required."""
        self._setup_admin()
        try:
            resp = test_client.patch(
                "/api/v1/admin/venues/venue_1/verification/doc_1",
                json={},
            )
            assert resp.status_code == 422
        finally:
            self._teardown_admin()


# ---------------------------------------------------------------------------
# E. Venue Spaces auth boundary
# ---------------------------------------------------------------------------

class TestVenueSpacesAuth:
    """Org mismatch must return 403 for space endpoints."""

    def test_create_space_wrong_org_returns_403(self, test_client: TestClient):
        resp = test_client.post(
            "/api/v1/organizations/org_other/venues/venue_1/spaces",
            json={"name": "Main Hall"},
        )
        assert resp.status_code == 403

    def test_list_spaces_wrong_org_returns_403(self, test_client: TestClient):
        resp = test_client.get(
            "/api/v1/organizations/org_other/venues/venue_1/spaces"
        )
        assert resp.status_code == 403

    def test_update_space_wrong_org_returns_403(self, test_client: TestClient):
        resp = test_client.patch(
            "/api/v1/organizations/org_other/venues/venue_1/spaces/space_1",
            json={"name": "Updated Hall"},
        )
        assert resp.status_code == 403

    def test_delete_space_wrong_org_returns_403(self, test_client: TestClient):
        resp = test_client.delete(
            "/api/v1/organizations/org_other/venues/venue_1/spaces/space_1"
        )
        assert resp.status_code == 403

    def test_set_pricing_wrong_org_returns_403(self, test_client: TestClient):
        resp = test_client.put(
            "/api/v1/organizations/org_other/venues/venue_1/spaces/space_1/pricing",
            json={"pricing": [{"rate_type": "hourly", "amount": 100, "currency": "USD"}]},
        )
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# F. Admin verification document status update
# ---------------------------------------------------------------------------

class TestAdminVerificationDoc:
    """PATCH /admin/venues/{venueId}/verification/{docId}"""

    def _setup_admin(self):
        app.dependency_overrides[deps.get_current_user] = _admin_override

    def _teardown_admin(self):
        app.dependency_overrides[deps.get_current_user] = lambda: MockTokenPayload()

    def test_accept_document_happy_path(
        self, monkeypatch, test_client: TestClient
    ):
        venue = _make_mock_venue()
        mock_crud = MagicMock()
        mock_crud.get.return_value = venue

        doc = MagicMock()
        doc.id = "doc_1"
        doc.venue_id = "venue_1"
        doc.status = "accepted"
        doc.admin_notes = "Looks good"

        mock_verification = MagicMock()
        mock_verification.update_status.return_value = doc

        monkeypatch.setattr(
            "app.api.v1.endpoints.venue_admin.crud_venue_obj", mock_crud
        )
        monkeypatch.setattr(
            "app.api.v1.endpoints.venue_admin.crud_verification",
            mock_verification,
        )

        self._setup_admin()
        try:
            resp = test_client.patch(
                "/api/v1/admin/venues/venue_1/verification/doc_1",
                json={"status": "accepted", "admin_notes": "Looks good"},
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["id"] == "doc_1"
            assert data["status"] == "accepted"
            assert data["admin_notes"] == "Looks good"
        finally:
            self._teardown_admin()

    def test_reject_document_happy_path(
        self, monkeypatch, test_client: TestClient
    ):
        venue = _make_mock_venue()
        mock_crud = MagicMock()
        mock_crud.get.return_value = venue

        doc = MagicMock()
        doc.id = "doc_1"
        doc.venue_id = "venue_1"
        doc.status = "rejected"
        doc.admin_notes = "Expired certificate"

        mock_verification = MagicMock()
        mock_verification.update_status.return_value = doc

        monkeypatch.setattr(
            "app.api.v1.endpoints.venue_admin.crud_venue_obj", mock_crud
        )
        monkeypatch.setattr(
            "app.api.v1.endpoints.venue_admin.crud_verification",
            mock_verification,
        )

        self._setup_admin()
        try:
            resp = test_client.patch(
                "/api/v1/admin/venues/venue_1/verification/doc_1",
                json={"status": "rejected", "admin_notes": "Expired certificate"},
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["status"] == "rejected"
        finally:
            self._teardown_admin()

    def test_document_not_found(self, monkeypatch, test_client: TestClient):
        venue = _make_mock_venue()
        mock_crud = MagicMock()
        mock_crud.get.return_value = venue

        mock_verification = MagicMock()
        mock_verification.update_status.return_value = None

        monkeypatch.setattr(
            "app.api.v1.endpoints.venue_admin.crud_venue_obj", mock_crud
        )
        monkeypatch.setattr(
            "app.api.v1.endpoints.venue_admin.crud_verification",
            mock_verification,
        )

        self._setup_admin()
        try:
            resp = test_client.patch(
                "/api/v1/admin/venues/venue_1/verification/nonexistent",
                json={"status": "accepted"},
            )
            assert resp.status_code == 404
        finally:
            self._teardown_admin()

    def test_venue_not_found_for_doc_update(
        self, monkeypatch, test_client: TestClient
    ):
        mock_crud = MagicMock()
        mock_crud.get.return_value = None
        monkeypatch.setattr(
            "app.api.v1.endpoints.venue_admin.crud_venue_obj", mock_crud
        )

        self._setup_admin()
        try:
            resp = test_client.patch(
                "/api/v1/admin/venues/no_venue/verification/doc_1",
                json={"status": "accepted"},
            )
            assert resp.status_code == 404
        finally:
            self._teardown_admin()

    def test_doc_belongs_to_different_venue(
        self, monkeypatch, test_client: TestClient
    ):
        """Doc exists but belongs to a different venue -> 404."""
        venue = _make_mock_venue(id="venue_1")
        mock_crud = MagicMock()
        mock_crud.get.return_value = venue

        doc = MagicMock()
        doc.id = "doc_1"
        doc.venue_id = "venue_OTHER"  # mismatch
        doc.status = "accepted"
        doc.admin_notes = None

        mock_verification = MagicMock()
        mock_verification.update_status.return_value = doc

        monkeypatch.setattr(
            "app.api.v1.endpoints.venue_admin.crud_venue_obj", mock_crud
        )
        monkeypatch.setattr(
            "app.api.v1.endpoints.venue_admin.crud_verification",
            mock_verification,
        )

        self._setup_admin()
        try:
            resp = test_client.patch(
                "/api/v1/admin/venues/venue_1/verification/doc_1",
                json={"status": "accepted"},
            )
            assert resp.status_code == 404
        finally:
            self._teardown_admin()


# ---------------------------------------------------------------------------
# G. Admin request-documents endpoint
# ---------------------------------------------------------------------------

class TestAdminRequestDocuments:

    def _setup_admin(self):
        app.dependency_overrides[deps.get_current_user] = _admin_override

    def _teardown_admin(self):
        app.dependency_overrides[deps.get_current_user] = lambda: MockTokenPayload()

    @patch("app.core.email.send_venue_document_request_email")
    def test_request_documents_happy_path(
        self, mock_email, monkeypatch, test_client: TestClient
    ):
        venue = _make_mock_venue(email="owner@example.com")
        mock_crud = MagicMock()
        mock_crud.get.return_value = venue
        monkeypatch.setattr(
            "app.api.v1.endpoints.venue_admin.crud_venue_obj", mock_crud
        )
        self._setup_admin()
        try:
            resp = test_client.post(
                "/api/v1/admin/venues/venue_1/request-documents",
                json={"message": "Please upload your business license."},
            )
            assert resp.status_code == 200
            assert resp.json()["venue_id"] == "venue_1"
        finally:
            self._teardown_admin()

    def test_request_documents_venue_not_found(
        self, monkeypatch, test_client: TestClient
    ):
        mock_crud = MagicMock()
        mock_crud.get.return_value = None
        monkeypatch.setattr(
            "app.api.v1.endpoints.venue_admin.crud_venue_obj", mock_crud
        )
        self._setup_admin()
        try:
            resp = test_client.post(
                "/api/v1/admin/venues/nope/request-documents",
                json={"message": "Send docs"},
            )
            assert resp.status_code == 404
        finally:
            self._teardown_admin()

    def test_request_documents_no_email(
        self, monkeypatch, test_client: TestClient
    ):
        """Venue without email -> 422."""
        venue = _make_mock_venue(email=None)
        mock_crud = MagicMock()
        mock_crud.get.return_value = venue
        monkeypatch.setattr(
            "app.api.v1.endpoints.venue_admin.crud_venue_obj", mock_crud
        )
        self._setup_admin()
        try:
            resp = test_client.post(
                "/api/v1/admin/venues/venue_1/request-documents",
                json={"message": "Send docs"},
            )
            assert resp.status_code == 422
            assert "email" in resp.json()["detail"].lower()
        finally:
            self._teardown_admin()
