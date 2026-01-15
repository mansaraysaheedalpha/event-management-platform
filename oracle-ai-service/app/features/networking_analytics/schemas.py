# app/features/networking_analytics/schemas.py
"""
Pydantic schemas for networking analytics API.
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class InterestCount(BaseModel):
    """Interest with connection count."""

    interest: str = Field(..., description="Interest name")
    count: int = Field(..., description="Number of connections from this interest")


class GoalPairCount(BaseModel):
    """Goal pair with connection count."""

    pair: list[str] = Field(..., description="Pair of goals that connected")
    count: int = Field(..., description="Number of connections from this pair")


class TierDistribution(BaseModel):
    """Distribution of profile tiers."""

    tier_0_pending: int = Field(0, description="Profiles pending enrichment")
    tier_1_rich: int = Field(0, description="Rich profiles (3+ sources)")
    tier_2_basic: int = Field(0, description="Basic profiles (1-2 sources)")
    tier_3_manual: int = Field(0, description="Manual profiles (no sources)")


class NetworkingAnalyticsResponse(BaseModel):
    """Complete networking analytics for an event."""

    event_id: str = Field(..., description="Event identifier")
    computed_at: datetime = Field(..., description="When analytics were computed")

    # Registration metrics
    total_attendees: int = Field(..., description="Total registered attendees")
    profiles_enriched: int = Field(..., description="Successfully enriched profiles")
    enrichment_rate: float = Field(..., description="Enrichment success rate (0-1)")
    tier_distribution: TierDistribution = Field(..., description="Profile tier breakdown")

    # Recommendation metrics
    recommendations_generated: int = Field(..., description="Total recommendations generated")
    recommendations_viewed: int = Field(..., description="Recommendations viewed by users")
    recommendation_view_rate: float = Field(..., description="View rate (0-1)")

    # Connection metrics
    total_pings: int = Field(..., description="Total ping requests sent")
    total_dms: int = Field(..., description="Total direct messages sent")
    total_connections: int = Field(..., description="Total connections made")
    connections_per_attendee: float = Field(..., description="Average connections per attendee")

    # Huddle metrics
    huddles_formed: int = Field(..., description="Total huddles created")
    huddle_invites_sent: int = Field(..., description="Huddle invitations sent")
    huddle_accept_rate: float = Field(..., description="Invitation accept rate (0-1)")
    huddle_attend_rate: float = Field(..., description="Attendance rate (0-1)")
    avg_huddle_size: float = Field(..., description="Average participants per huddle")

    # Follow-up metrics
    follow_ups_sent: int = Field(..., description="Follow-up messages sent post-event")
    follow_up_response_rate: float = Field(..., description="Response rate (0-1)")

    # Top matching factors
    top_interests: list[InterestCount] = Field(..., description="Interests driving most connections")
    top_goal_pairs: list[GoalPairCount] = Field(..., description="Goal combinations with most connections")

    # Benchmarks
    benchmark_comparison: Optional[dict] = Field(None, description="Comparison to industry averages")


class AnalyticsSummaryResponse(BaseModel):
    """Summary analytics for quick dashboard view."""

    event_id: str
    total_attendees: int
    total_connections: int
    connections_per_attendee: float
    enrichment_rate: float
    recommendation_view_rate: float
    computed_at: datetime


class AnalyticsExportResponse(BaseModel):
    """Response containing exported analytics data."""

    event_id: str = Field(..., description="Event identifier")
    format: str = Field(..., description="Export format (json, csv)")
    data: dict = Field(..., description="Exported analytics data")
    generated_at: datetime = Field(..., description="When export was generated")


class AnalyticsComputeRequest(BaseModel):
    """Request to compute/refresh analytics."""

    force_refresh: bool = Field(
        False,
        description="Force recomputation even if cached",
    )


class BenchmarkData(BaseModel):
    """Industry benchmark comparison data."""

    metric: str = Field(..., description="Metric name")
    your_value: float = Field(..., description="Your event's value")
    industry_avg: float = Field(..., description="Industry average")
    target: float = Field(..., description="Target value")
    is_above_target: bool = Field(..., description="Whether you're meeting the target")
