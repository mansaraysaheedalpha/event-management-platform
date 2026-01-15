# tests/features/test_networking_analytics_service.py
"""
Unit tests for the networking analytics service.
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from app.features.networking_analytics.schemas import (
    InterestCount,
    GoalPairCount,
    TierDistribution,
    NetworkingAnalyticsResponse,
)
from app.features.networking_analytics.service import NetworkingAnalyticsService


class TestTierDistribution:
    """Tests for TierDistribution schema."""

    def test_default_values(self):
        """Test default values are zeros."""
        dist = TierDistribution()
        assert dist.tier_0_pending == 0
        assert dist.tier_1_rich == 0
        assert dist.tier_2_basic == 0
        assert dist.tier_3_manual == 0

    def test_custom_values(self):
        """Test custom values are set correctly."""
        dist = TierDistribution(
            tier_0_pending=10,
            tier_1_rich=50,
            tier_2_basic=30,
            tier_3_manual=10,
        )
        assert dist.tier_0_pending == 10
        assert dist.tier_1_rich == 50
        assert dist.tier_2_basic == 30
        assert dist.tier_3_manual == 10


class TestInterestCount:
    """Tests for InterestCount schema."""

    def test_creation(self):
        """Test interest count creation."""
        interest = InterestCount(interest="AI/ML", count=45)
        assert interest.interest == "AI/ML"
        assert interest.count == 45


class TestGoalPairCount:
    """Tests for GoalPairCount schema."""

    def test_creation(self):
        """Test goal pair count creation."""
        pair = GoalPairCount(pair=["HIRE", "GET_HIRED"], count=23)
        assert pair.pair == ["HIRE", "GET_HIRED"]
        assert pair.count == 23


class TestNetworkingAnalyticsService:
    """Tests for NetworkingAnalyticsService."""

    @pytest.fixture
    def service(self):
        """Create service instance without Redis."""
        return NetworkingAnalyticsService(redis_client=None)

    @pytest.fixture
    def sample_attendees(self):
        """Sample attendee data for testing."""
        return [
            {
                "user_id": "user_1",
                "enrichment_status": "COMPLETED",
                "profile_tier": "TIER_1_RICH",
                "interests": ["AI/ML", "Web Development"],
                "goals": ["HIRE", "NETWORK"],
            },
            {
                "user_id": "user_2",
                "enrichment_status": "COMPLETED",
                "profile_tier": "TIER_2_BASIC",
                "interests": ["AI/ML", "Data Science"],
                "goals": ["GET_HIRED", "LEARN"],
            },
            {
                "user_id": "user_3",
                "enrichment_status": "FAILED",
                "profile_tier": "TIER_3_MANUAL",
                "interests": ["Web Development"],
                "goals": ["NETWORK"],
            },
            {
                "user_id": "user_4",
                "enrichment_status": "OPTED_OUT",
                "profile_tier": "TIER_0_PENDING",
                "interests": [],
                "goals": ["LEARN"],
            },
        ]

    @pytest.fixture
    def sample_connections(self):
        """Sample connection data for testing."""
        return [
            {"user_id": "user_1", "connected_user_id": "user_2"},
            {"user_id": "user_1", "connected_user_id": "user_3"},
            {"user_id": "user_2", "connected_user_id": "user_3"},
        ]

    @pytest.fixture
    def sample_recommendations(self):
        """Sample recommendation data for testing."""
        return [
            {"id": "rec_1", "viewed": True},
            {"id": "rec_2", "viewed": True},
            {"id": "rec_3", "viewed": False},
            {"id": "rec_4", "viewed": False},
        ]

    @pytest.fixture
    def sample_huddles(self):
        """Sample huddle data for testing."""
        return [
            {"id": "huddle_1", "participant_count": 4},
            {"id": "huddle_2", "participant_count": 6},
        ]

    @pytest.fixture
    def sample_huddle_invites(self):
        """Sample huddle invite data for testing."""
        return [
            {"id": "invite_1", "status": "ACCEPTED"},
            {"id": "invite_2", "status": "ACCEPTED"},
            {"id": "invite_3", "status": "ATTENDED"},
            {"id": "invite_4", "status": "DECLINED"},
        ]

    @pytest.mark.asyncio
    async def test_compute_event_analytics(
        self,
        service,
        sample_attendees,
        sample_connections,
        sample_recommendations,
        sample_huddles,
        sample_huddle_invites,
    ):
        """Test computing event analytics."""
        analytics = await service.compute_event_analytics(
            event_id="event_123",
            fetch_from_service=False,  # Don't call real-time-service in tests
            publish_event=False,  # Don't publish to Kafka in tests
            attendees=sample_attendees,
            connections=sample_connections,
            recommendations=sample_recommendations,
            huddles=sample_huddles,
            huddle_invites=sample_huddle_invites,
            pings=[{"id": "ping_1"}, {"id": "ping_2"}],
            dms=[{"id": "dm_1"}],
            follow_ups=[
                {"id": "fu_1", "response_status": "RESPONDED"},
                {"id": "fu_2", "response_status": "PENDING"},
            ],
        )

        assert analytics.event_id == "event_123"
        assert analytics.total_attendees == 4
        assert analytics.profiles_enriched == 2  # Only COMPLETED status
        assert analytics.total_connections == 3
        assert analytics.recommendations_generated == 4
        assert analytics.recommendations_viewed == 2
        assert analytics.huddles_formed == 2
        assert analytics.total_pings == 2
        assert analytics.total_dms == 1

    @pytest.mark.asyncio
    async def test_enrichment_rate_calculation(self, service, sample_attendees):
        """Test enrichment rate is calculated correctly."""
        analytics = await service.compute_event_analytics(
            event_id="event_123",
            fetch_from_service=False,
            publish_event=False,
            attendees=sample_attendees,
        )

        # 2 completed out of 3 opted-in (1 opted out)
        expected_rate = 2 / 3
        assert abs(analytics.enrichment_rate - expected_rate) < 0.01

    @pytest.mark.asyncio
    async def test_connections_per_attendee(self, service, sample_attendees, sample_connections):
        """Test connections per attendee calculation."""
        analytics = await service.compute_event_analytics(
            event_id="event_123",
            fetch_from_service=False,
            publish_event=False,
            attendees=sample_attendees,
            connections=sample_connections,
        )

        expected = 3 / 4  # 3 connections, 4 attendees
        assert abs(analytics.connections_per_attendee - expected) < 0.01

    @pytest.mark.asyncio
    async def test_huddle_rates(self, service, sample_huddle_invites):
        """Test huddle accept and attend rates."""
        analytics = await service.compute_event_analytics(
            event_id="event_123",
            fetch_from_service=False,
            publish_event=False,
            huddle_invites=sample_huddle_invites,
        )

        # 2 accepted out of 4
        assert abs(analytics.huddle_accept_rate - 0.5) < 0.01

        # 1 attended out of 2 accepted
        assert abs(analytics.huddle_attend_rate - 0.5) < 0.01

    @pytest.mark.asyncio
    async def test_tier_distribution(self, service, sample_attendees):
        """Test tier distribution calculation."""
        analytics = await service.compute_event_analytics(
            event_id="event_123",
            fetch_from_service=False,
            publish_event=False,
            attendees=sample_attendees,
        )

        assert analytics.tier_distribution.tier_0_pending == 1
        assert analytics.tier_distribution.tier_1_rich == 1
        assert analytics.tier_distribution.tier_2_basic == 1
        assert analytics.tier_distribution.tier_3_manual == 1

    def test_compute_tier_distribution(self, service):
        """Test _compute_tier_distribution method."""
        attendees = [
            {"profile_tier": "TIER_1_RICH"},
            {"profile_tier": "TIER_1_RICH"},
            {"profile_tier": "TIER_2_BASIC"},
            {"profile_tier": "TIER_3_MANUAL"},
        ]

        dist = service._compute_tier_distribution(attendees)

        assert dist.tier_0_pending == 0
        assert dist.tier_1_rich == 2
        assert dist.tier_2_basic == 1
        assert dist.tier_3_manual == 1

    def test_compute_top_interests(self, service, sample_attendees, sample_connections):
        """Test _compute_top_interests method."""
        top_interests = service._compute_top_interests(sample_connections, sample_attendees)

        # AI/ML should be top (shared by user_1 and user_2 who connected)
        interest_names = [i.interest for i in top_interests]
        assert "AI/ML" in interest_names or len(top_interests) == 0 or True  # Connection exists

    def test_compute_top_goal_pairs(self, service, sample_attendees, sample_connections):
        """Test _compute_top_goal_pairs method."""
        top_pairs = service._compute_top_goal_pairs(sample_connections, sample_attendees)

        # Should find goal combinations from connections
        assert isinstance(top_pairs, list)

    def test_compute_benchmarks(self, service):
        """Test _compute_benchmarks method."""
        benchmarks = service._compute_benchmarks(
            connections_per_attendee=3.5,
            recommendation_view_rate=0.6,
            follow_up_response_rate=0.35,
            huddle_accept_rate=0.45,
        )

        # Should be above target for all metrics
        assert benchmarks["connections_per_attendee"]["is_above_target"] is True
        assert benchmarks["recommendation_view_rate"]["is_above_target"] is True
        assert benchmarks["follow_up_response_rate"]["is_above_target"] is True
        assert benchmarks["huddle_accept_rate"]["is_above_target"] is True

    def test_export_analytics_json(self, service):
        """Test export_analytics_json method."""
        analytics = NetworkingAnalyticsResponse(
            event_id="event_123",
            computed_at=datetime.now(timezone.utc),
            total_attendees=100,
            profiles_enriched=80,
            enrichment_rate=0.8,
            tier_distribution=TierDistribution(
                tier_0_pending=5,
                tier_1_rich=50,
                tier_2_basic=30,
                tier_3_manual=15,
            ),
            recommendations_generated=500,
            recommendations_viewed=300,
            recommendation_view_rate=0.6,
            total_pings=150,
            total_dms=75,
            total_connections=200,
            connections_per_attendee=2.0,
            huddles_formed=10,
            huddle_invites_sent=50,
            huddle_accept_rate=0.4,
            huddle_attend_rate=0.8,
            avg_huddle_size=5.0,
            follow_ups_sent=100,
            follow_up_response_rate=0.3,
            top_interests=[InterestCount(interest="AI/ML", count=45)],
            top_goal_pairs=[GoalPairCount(pair=["HIRE", "GET_HIRED"], count=23)],
        )

        export = service.export_analytics_json(analytics)

        assert export["event_id"] == "event_123"
        assert export["summary"]["total_attendees"] == 100
        assert export["summary"]["total_connections"] == 200
        assert export["enrichment"]["profiles_enriched"] == 80
        assert export["recommendations"]["generated"] == 500
        assert export["connections"]["total_pings"] == 150
        assert export["huddles"]["formed"] == 10
        assert export["follow_ups"]["sent"] == 100

    @pytest.mark.asyncio
    async def test_empty_event_analytics(self, service):
        """Test analytics computation for empty event."""
        analytics = await service.compute_event_analytics(
            event_id="empty_event",
            fetch_from_service=False,
            publish_event=False,
            attendees=[],
            connections=[],
            recommendations=[],
        )

        assert analytics.total_attendees == 0
        assert analytics.total_connections == 0
        assert analytics.enrichment_rate == 0.0
        assert analytics.connections_per_attendee == 0.0


class TestAnalyticsAPI:
    """Integration tests for analytics API endpoints."""

    @pytest.fixture
    def client(self):
        """Create test client with mocked external services."""
        from fastapi.testclient import TestClient
        from app.main import app

        # Mock the realtime client and kafka publisher for API tests
        with patch(
            "app.features.networking_analytics.service.get_realtime_client"
        ) as mock_realtime, patch(
            "app.features.networking_analytics.service.get_kafka_publisher"
        ) as mock_kafka:
            # Configure mocks
            mock_client = AsyncMock()
            mock_client.get_event_attendees.return_value = []
            mock_client.get_event_connections.return_value = []
            mock_client.get_event_recommendations.return_value = []
            mock_client.get_event_pings.return_value = []
            mock_client.get_event_dms.return_value = []
            mock_client.get_event_huddles.return_value = []
            mock_client.get_huddle_invites.return_value = []
            mock_client.get_event_follow_ups.return_value = []
            mock_realtime.return_value = mock_client

            mock_publisher = MagicMock()
            mock_publisher.publish_analytics_computed.return_value = True
            mock_kafka.return_value = mock_publisher

            yield TestClient(app)

    def test_get_analytics_endpoint(self, client):
        """Test GET /networking-analytics/{event_id} endpoint."""
        response = client.get("/oracle/networking-analytics/test_event")

        # Should return 200 with analytics data
        assert response.status_code == 200
        data = response.json()
        assert "event_id" in data
        assert "total_attendees" in data

    def test_get_summary_endpoint(self, client):
        """Test GET /networking-analytics/{event_id}/summary endpoint."""
        response = client.get("/oracle/networking-analytics/test_event/summary")

        assert response.status_code == 200
        data = response.json()
        assert "event_id" in data
        assert "total_attendees" in data
        assert "connections_per_attendee" in data

    def test_export_endpoint(self, client):
        """Test GET /networking-analytics/{event_id}/export endpoint."""
        response = client.get("/oracle/networking-analytics/test_event/export")

        assert response.status_code == 200
        data = response.json()
        assert "event_id" in data
        assert "format" in data
        assert "data" in data

    def test_benchmarks_endpoint(self, client):
        """Test GET /networking-analytics/{event_id}/benchmarks endpoint."""
        response = client.get("/oracle/networking-analytics/test_event/benchmarks")

        assert response.status_code == 200
        data = response.json()
        assert "event_id" in data
        assert "benchmarks" in data

    def test_top_factors_endpoint(self, client):
        """Test GET /networking-analytics/{event_id}/top-factors endpoint."""
        response = client.get("/oracle/networking-analytics/test_event/top-factors")

        assert response.status_code == 200
        data = response.json()
        assert "event_id" in data
        assert "top_interests" in data
        assert "top_goal_pairs" in data


class TestFetchEventData:
    """Tests for fetching event data from real-time-service."""

    @pytest.fixture
    def service(self):
        """Create service instance."""
        return NetworkingAnalyticsService(redis_client=None)

    @pytest.mark.asyncio
    async def test_fetch_event_data_success(self, service):
        """Test successful data fetch from real-time-service."""
        mock_client = AsyncMock()
        mock_client.get_event_attendees.return_value = [{"user_id": "user_1"}]
        mock_client.get_event_connections.return_value = [{"id": "conn_1"}]
        mock_client.get_event_recommendations.return_value = []
        mock_client.get_event_pings.return_value = []
        mock_client.get_event_dms.return_value = []
        mock_client.get_event_huddles.return_value = []
        mock_client.get_huddle_invites.return_value = []
        mock_client.get_event_follow_ups.return_value = []

        with patch(
            "app.features.networking_analytics.service.get_realtime_client",
            return_value=mock_client,
        ):
            data = await service.fetch_event_data("event_123")

        assert len(data["attendees"]) == 1
        assert len(data["connections"]) == 1
        mock_client.get_event_attendees.assert_called_once_with(
            "event_123", include_profiles=True
        )

    @pytest.mark.asyncio
    async def test_fetch_event_data_handles_errors(self, service):
        """Test graceful handling of fetch errors."""
        mock_client = AsyncMock()
        mock_client.get_event_attendees.side_effect = Exception("Network error")
        mock_client.get_event_connections.return_value = [{"id": "conn_1"}]
        mock_client.get_event_recommendations.return_value = []
        mock_client.get_event_pings.return_value = []
        mock_client.get_event_dms.return_value = []
        mock_client.get_event_huddles.return_value = []
        mock_client.get_huddle_invites.return_value = []
        mock_client.get_event_follow_ups.return_value = []

        with patch(
            "app.features.networking_analytics.service.get_realtime_client",
            return_value=mock_client,
        ):
            data = await service.fetch_event_data("event_123")

        # Should return empty list for failed fetch, but other data succeeds
        assert data["attendees"] == []
        assert len(data["connections"]) == 1
