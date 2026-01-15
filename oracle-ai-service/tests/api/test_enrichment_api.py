# tests/api/test_enrichment_api.py
"""
Integration tests for the enrichment API endpoints.
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from fastapi.testclient import TestClient


class TestEnrichmentAPI:
    """Integration tests for enrichment API endpoints."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        from app.main import app
        return TestClient(app)

    @pytest.fixture
    def mock_enrichment_service(self):
        """Mock the enrichment service."""
        with patch(
            "app.features.enrichment.router.get_enrichment_service"
        ) as mock:
            service = MagicMock()
            mock.return_value = service
            yield service

    def test_enrich_user_success(self, client, mock_enrichment_service):
        """Test POST /enrichment/{user_id} success."""
        mock_enrichment_service.enrich_user_async = AsyncMock(
            return_value={
                "status": "processing",
                "message": "Enrichment started in background",
                "task_id": "task_123",
            }
        )

        response = client.post(
            "/oracle/enrichment/user_123",
            json={
                "name": "John Doe",
                "email": "john@example.com",
                "company": "Acme Corp",
                "role": "Software Engineer",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "processing"
        assert "task_id" in data

    def test_enrich_user_with_profiles(self, client, mock_enrichment_service):
        """Test enrichment with optional profile links."""
        mock_enrichment_service.enrich_user_async = AsyncMock(
            return_value={
                "status": "processing",
                "message": "Enrichment started",
                "task_id": "task_456",
            }
        )

        response = client.post(
            "/oracle/enrichment/user_123",
            json={
                "name": "John Doe",
                "email": "john@example.com",
                "company": "Acme Corp",
                "role": "Software Engineer",
                "linkedin_url": "https://linkedin.com/in/johndoe",
                "github_username": "johndoe",
                "twitter_handle": "johndoe",
            },
        )

        assert response.status_code == 200

    def test_enrich_user_validation_error(self, client):
        """Test validation error for missing required fields."""
        response = client.post(
            "/oracle/enrichment/user_123",
            json={
                "name": "John Doe",
                # Missing email, company, role
            },
        )

        assert response.status_code == 422  # Validation error

    def test_enrich_user_invalid_linkedin_url(self, client):
        """Test validation error for invalid LinkedIn URL."""
        response = client.post(
            "/oracle/enrichment/user_123",
            json={
                "name": "John Doe",
                "email": "john@example.com",
                "company": "Acme Corp",
                "role": "Engineer",
                "linkedin_url": "not-a-valid-url",
            },
        )

        assert response.status_code == 422

    def test_enrichment_status_endpoint(self, client, mock_enrichment_service):
        """Test GET /enrichment/status/{user_id} endpoint."""
        mock_enrichment_service.get_enrichment_status = MagicMock(
            return_value={
                "user_id": "user_123",
                "status": "COMPLETED",
                "profile_tier": "TIER_1_RICH",
                "enriched_at": None,
                "sources": ["linkedin", "github"],
            }
        )

        response = client.get("/oracle/enrichment/status/user_123")

        assert response.status_code == 200
        data = response.json()
        assert data["user_id"] == "user_123"
        assert data["status"] == "COMPLETED"

    def test_batch_enrichment_endpoint(self, client, mock_enrichment_service):
        """Test POST /enrichment/batch endpoint."""
        mock_enrichment_service.enrich_event_attendees = AsyncMock(
            return_value={
                "event_id": "event_123",
                "status": "queued",
                "message": "Enrichment queued for 10 attendees",
                "task_id": "batch_task_123",
            }
        )

        response = client.post(
            "/oracle/enrichment/batch",
            json={
                "event_id": "event_123",
                "attendees": [
                    {
                        "user_id": "user_1",
                        "name": "John Doe",
                        "email": "john@example.com",
                        "company": "Acme",
                        "role": "Engineer",
                    },
                    {
                        "user_id": "user_2",
                        "name": "Jane Smith",
                        "email": "jane@example.com",
                        "company": "Tech Inc",
                        "role": "Designer",
                    },
                ],
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["event_id"] == "event_123"

    def test_enrichment_health_endpoint(self, client):
        """Test GET /enrichment/health endpoint."""
        with patch("app.features.enrichment.router.settings") as mock_settings:
            mock_settings.enrichment_enabled = True
            mock_settings.TAVILY_API_KEY = "test_key"
            mock_settings.ANTHROPIC_API_KEY = "test_key"
            mock_settings.GITHUB_PUBLIC_API_TOKEN = None

            with patch(
                "app.features.enrichment.router.get_all_breaker_stats",
                new_callable=AsyncMock,
            ) as mock_breakers:
                mock_breakers.return_value = []

                response = client.get("/oracle/enrichment/health")

                assert response.status_code == 200
                data = response.json()
                assert "enabled" in data
                assert "tavily_configured" in data


class TestEnrichmentRateLimiting:
    """Tests for enrichment rate limiting."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        from app.main import app
        return TestClient(app)

    def test_rate_limit_exceeded(self, client):
        """Test 429 response when rate limit exceeded."""
        with patch(
            "app.features.enrichment.service.get_user_enrichment_limiter"
        ) as mock_limiter:
            from app.core.exceptions import UserRateLimitError

            limiter = AsyncMock()
            limiter.acquire = AsyncMock(
                side_effect=UserRateLimitError(
                    user_id="user_123",
                    limit=5,
                    period_seconds=3600,
                )
            )
            mock_limiter.return_value = limiter

            with patch("app.features.enrichment.router.settings") as mock_settings:
                mock_settings.enrichment_enabled = True

                with patch(
                    "app.features.enrichment.router.get_enrichment_service"
                ) as mock_service:
                    service = MagicMock()
                    service.enrich_user_async = AsyncMock(
                        side_effect=UserRateLimitError(
                            user_id="user_123",
                            limit=5,
                            period_seconds=3600,
                        )
                    )
                    mock_service.return_value = service

                    response = client.post(
                        "/oracle/enrichment/user_123",
                        json={
                            "name": "John Doe",
                            "email": "john@example.com",
                            "company": "Acme",
                            "role": "Engineer",
                        },
                    )

                    assert response.status_code == 429


class TestEnrichmentServiceDisabled:
    """Tests for when enrichment service is disabled."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        from app.main import app
        return TestClient(app)

    def test_503_when_disabled(self, client):
        """Test 503 response when enrichment is disabled."""
        with patch(
            "app.features.enrichment.router.get_enrichment_service"
        ) as mock_service:
            from app.core.exceptions import EnrichmentDisabledError

            service = MagicMock()
            service.enrich_user_async = AsyncMock(
                side_effect=EnrichmentDisabledError()
            )
            mock_service.return_value = service

            response = client.post(
                "/oracle/enrichment/user_123",
                json={
                    "name": "John Doe",
                    "email": "john@example.com",
                    "company": "Acme",
                    "role": "Engineer",
                },
            )

            assert response.status_code == 503
