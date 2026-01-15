# app/integrations/__init__.py
"""
Service-to-service integration clients.

Provides typed clients for communicating with other microservices:
- real-time-service: User profiles, connections, recommendations
- event-lifecycle-service: Event data, attendees
"""

from app.integrations.realtime_client import RealtimeServiceClient
from app.integrations.kafka_publisher import KafkaEventPublisher
from app.integrations.events import (
    EnrichmentCompletedEvent,
    ProfileUpdatedEvent,
    AnalyticsComputedEvent,
)

__all__ = [
    "RealtimeServiceClient",
    "KafkaEventPublisher",
    "EnrichmentCompletedEvent",
    "ProfileUpdatedEvent",
    "AnalyticsComputedEvent",
]
