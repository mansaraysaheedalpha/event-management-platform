# app/integrations/events.py
"""
Event schemas for inter-service communication via Kafka.

These events are consumed by:
- real-time-service: To update user profiles, send notifications
- globalconnect (frontend): Via WebSocket for real-time updates
"""

from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class EventType(str, Enum):
    """Event types published by oracle-ai-service."""

    # Enrichment events
    ENRICHMENT_STARTED = "enrichment.started"
    ENRICHMENT_COMPLETED = "enrichment.completed"
    ENRICHMENT_FAILED = "enrichment.failed"

    # Profile events
    PROFILE_UPDATED = "profile.updated"
    PROFILE_TIER_CHANGED = "profile.tier_changed"

    # Analytics events
    ANALYTICS_COMPUTED = "analytics.computed"

    # Recommendation events
    RECOMMENDATIONS_GENERATED = "recommendations.generated"


class BaseEvent(BaseModel):
    """Base event schema with common fields."""

    event_type: EventType
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    correlation_id: Optional[str] = None
    source: str = "oracle-ai-service"


class EnrichmentStartedEvent(BaseEvent):
    """Published when enrichment begins for a user."""

    event_type: EventType = EventType.ENRICHMENT_STARTED
    user_id: str
    event_id: Optional[str] = None  # If triggered for specific event


class EnrichmentCompletedEvent(BaseEvent):
    """
    Published when profile enrichment completes successfully.

    Consumed by real-time-service to:
    1. Update UserProfile in database
    2. Send WebSocket notification to user
    3. Trigger recommendation regeneration
    """

    event_type: EventType = EventType.ENRICHMENT_COMPLETED
    user_id: str

    # Profile tier assignment
    profile_tier: str  # TIER_1_RICH, TIER_2_BASIC, TIER_3_MANUAL

    # Sources found
    sources_found: list[str] = Field(default_factory=list)

    # Enriched data (matches Prisma UserProfile schema)
    enriched_data: dict[str, Any] = Field(
        default_factory=dict,
        description="Enriched profile fields matching UserProfile schema",
    )

    # Processing metadata
    processing_time_seconds: Optional[float] = None


class EnrichmentFailedEvent(BaseEvent):
    """Published when enrichment fails."""

    event_type: EventType = EventType.ENRICHMENT_FAILED
    user_id: str
    error: str
    retry_count: int = 0
    will_retry: bool = False


class ProfileUpdatedEvent(BaseEvent):
    """
    Published when a user profile is updated.

    Used to sync profile changes across services.
    """

    event_type: EventType = EventType.PROFILE_UPDATED
    user_id: str
    updated_fields: list[str]
    profile_data: dict[str, Any]


class ProfileTierChangedEvent(BaseEvent):
    """Published when a user's profile tier changes."""

    event_type: EventType = EventType.PROFILE_TIER_CHANGED
    user_id: str
    old_tier: str
    new_tier: str
    reason: str  # e.g., "enrichment_completed", "manual_update"


class AnalyticsComputedEvent(BaseEvent):
    """
    Published when networking analytics are computed for an event.

    Consumed by:
    - globalconnect frontend: To update organizer dashboard
    """

    event_type: EventType = EventType.ANALYTICS_COMPUTED
    event_id: str

    # Summary metrics for real-time display
    total_attendees: int
    total_connections: int
    connections_per_attendee: float
    enrichment_rate: float
    recommendation_view_rate: float

    # Indicates if full data should be fetched
    full_data_available: bool = True


class RecommendationsGeneratedEvent(BaseEvent):
    """
    Published when AI recommendations are generated for a user.

    Consumed by real-time-service to:
    1. Store recommendations in database
    2. Send push notification to user
    """

    event_type: EventType = EventType.RECOMMENDATIONS_GENERATED
    user_id: str
    event_id: str
    recommendation_count: int
    top_match_score: int  # Highest match score in batch
