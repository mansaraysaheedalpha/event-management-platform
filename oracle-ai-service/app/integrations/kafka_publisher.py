# app/integrations/kafka_publisher.py
"""
Kafka event publisher for async inter-service communication.

Publishes events to topics that are consumed by:
- real-time-service
- event-lifecycle-service
- Frontend via WebSocket bridge
"""

import json
import logging
from typing import Optional

from kafka import KafkaProducer
from kafka.errors import KafkaError

from app.core.config import settings
from app.integrations.events import (
    BaseEvent,
    EnrichmentCompletedEvent,
    EnrichmentFailedEvent,
    EnrichmentStartedEvent,
    AnalyticsComputedEvent,
    ProfileUpdatedEvent,
    RecommendationsGeneratedEvent,
)

logger = logging.getLogger(__name__)


class KafkaEventPublisher:
    """
    Kafka event publisher with automatic serialization.

    Topics:
    - oracle.enrichment: Enrichment lifecycle events
    - oracle.profile: Profile update events
    - oracle.analytics: Analytics computation events
    - oracle.recommendations: Recommendation events
    """

    TOPICS = {
        "enrichment": "oracle.enrichment",
        "profile": "oracle.profile",
        "analytics": "oracle.analytics",
        "recommendations": "oracle.recommendations",
    }

    def __init__(self):
        """Initialize Kafka producer."""
        self._producer: Optional[KafkaProducer] = None
        self._connected = False

    def _get_producer(self) -> KafkaProducer:
        """Get or create Kafka producer with lazy initialization."""
        if self._producer is None:
            try:
                self._producer = KafkaProducer(
                    bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS.split(","),
                    value_serializer=lambda v: json.dumps(v, default=str).encode("utf-8"),
                    key_serializer=lambda k: k.encode("utf-8") if k else None,
                    acks="all",  # Wait for all replicas
                    retries=3,
                    retry_backoff_ms=100,
                )
                self._connected = True
                logger.info("Kafka producer connected")
            except KafkaError as e:
                logger.error(f"Failed to connect to Kafka: {e}")
                raise

        return self._producer

    def _publish(self, topic: str, event: BaseEvent, key: Optional[str] = None) -> bool:
        """
        Publish event to Kafka topic.

        Args:
            topic: Kafka topic name
            event: Event to publish
            key: Optional partition key (for ordering)

        Returns:
            True if published successfully
        """
        try:
            producer = self._get_producer()
            future = producer.send(
                topic,
                value=event.model_dump(),
                key=key,
            )
            # Wait for send to complete (with timeout)
            future.get(timeout=10)

            logger.debug(
                f"Published {event.event_type.value} to {topic}",
                extra={"event_type": event.event_type.value, "topic": topic},
            )
            return True

        except KafkaError as e:
            logger.error(
                f"Failed to publish event to Kafka: {e}",
                extra={"event_type": event.event_type.value, "topic": topic},
            )
            return False

    # ===========================================
    # Enrichment Events
    # ===========================================

    def publish_enrichment_started(
        self,
        user_id: str,
        event_id: Optional[str] = None,
        correlation_id: Optional[str] = None,
    ) -> bool:
        """Publish enrichment started event."""
        event = EnrichmentStartedEvent(
            user_id=user_id,
            event_id=event_id,
            correlation_id=correlation_id,
        )
        return self._publish(
            self.TOPICS["enrichment"],
            event,
            key=user_id,
        )

    def publish_enrichment_completed(
        self,
        user_id: str,
        profile_tier: str,
        sources_found: list[str],
        enriched_data: dict,
        processing_time_seconds: Optional[float] = None,
        correlation_id: Optional[str] = None,
    ) -> bool:
        """
        Publish enrichment completed event.

        This triggers the real-time-service to:
        1. Update the UserProfile in Prisma
        2. Send notification to user
        3. Regenerate recommendations
        """
        event = EnrichmentCompletedEvent(
            user_id=user_id,
            profile_tier=profile_tier,
            sources_found=sources_found,
            enriched_data=enriched_data,
            processing_time_seconds=processing_time_seconds,
            correlation_id=correlation_id,
        )
        return self._publish(
            self.TOPICS["enrichment"],
            event,
            key=user_id,
        )

    def publish_enrichment_failed(
        self,
        user_id: str,
        error: str,
        retry_count: int = 0,
        will_retry: bool = False,
        correlation_id: Optional[str] = None,
    ) -> bool:
        """Publish enrichment failed event."""
        event = EnrichmentFailedEvent(
            user_id=user_id,
            error=error,
            retry_count=retry_count,
            will_retry=will_retry,
            correlation_id=correlation_id,
        )
        return self._publish(
            self.TOPICS["enrichment"],
            event,
            key=user_id,
        )

    # ===========================================
    # Profile Events
    # ===========================================

    def publish_profile_updated(
        self,
        user_id: str,
        updated_fields: list[str],
        profile_data: dict,
        correlation_id: Optional[str] = None,
    ) -> bool:
        """Publish profile updated event."""
        event = ProfileUpdatedEvent(
            user_id=user_id,
            updated_fields=updated_fields,
            profile_data=profile_data,
            correlation_id=correlation_id,
        )
        return self._publish(
            self.TOPICS["profile"],
            event,
            key=user_id,
        )

    # ===========================================
    # Analytics Events
    # ===========================================

    def publish_analytics_computed(
        self,
        event_id: str,
        total_attendees: int,
        total_connections: int,
        connections_per_attendee: float,
        enrichment_rate: float,
        recommendation_view_rate: float,
        correlation_id: Optional[str] = None,
    ) -> bool:
        """
        Publish analytics computed event.

        Triggers frontend dashboard refresh.
        """
        event = AnalyticsComputedEvent(
            event_id=event_id,
            total_attendees=total_attendees,
            total_connections=total_connections,
            connections_per_attendee=connections_per_attendee,
            enrichment_rate=enrichment_rate,
            recommendation_view_rate=recommendation_view_rate,
            correlation_id=correlation_id,
        )
        return self._publish(
            self.TOPICS["analytics"],
            event,
            key=event_id,
        )

    # ===========================================
    # Recommendation Events
    # ===========================================

    def publish_recommendations_generated(
        self,
        user_id: str,
        event_id: str,
        recommendation_count: int,
        top_match_score: int,
        correlation_id: Optional[str] = None,
    ) -> bool:
        """Publish recommendations generated event."""
        event = RecommendationsGeneratedEvent(
            user_id=user_id,
            event_id=event_id,
            recommendation_count=recommendation_count,
            top_match_score=top_match_score,
            correlation_id=correlation_id,
        )
        return self._publish(
            self.TOPICS["recommendations"],
            event,
            key=user_id,
        )

    def close(self) -> None:
        """Close Kafka producer."""
        if self._producer:
            self._producer.flush()
            self._producer.close()
            self._producer = None
            self._connected = False
            logger.info("Kafka producer closed")


# Singleton instance
_publisher: Optional[KafkaEventPublisher] = None


def get_kafka_publisher() -> KafkaEventPublisher:
    """Get or create Kafka publisher singleton."""
    global _publisher
    if _publisher is None:
        _publisher = KafkaEventPublisher()
    return _publisher
