"""
Pydantic models for Redis event validation
Ensures incoming Redis Pub/Sub events are properly validated before processing
"""
import logging
from pydantic import BaseModel, Field, validator
from typing import Optional, Any, Dict, Literal, Union
from datetime import datetime
from enum import Enum

logger = logging.getLogger(__name__)


# =====================
# Agent Notification Models (for publishing to Redis)
# =====================

class AnomalyType(str, Enum):
    """Types of anomalies detected by the engagement agent"""
    ENGAGEMENT_DROP = "ENGAGEMENT_DROP"
    SUDDEN_SPIKE = "SUDDEN_SPIKE"
    SENTIMENT_SHIFT = "SENTIMENT_SHIFT"
    PARTICIPATION_DECLINE = "PARTICIPATION_DECLINE"


class InterventionType(str, Enum):
    """Types of interventions executed by the engagement agent"""
    POLL = "POLL"
    CHAT_PROMPT = "CHAT_PROMPT"
    NUDGE = "NUDGE"
    CONTENT_SUGGESTION = "CONTENT_SUGGESTION"


class NotificationSeverity(str, Enum):
    """Severity levels for agent notifications"""
    CRITICAL = "CRITICAL"
    WARNING = "WARNING"
    INFO = "INFO"


class AnomalyDetectedNotification(BaseModel):
    """
    Notification published when an anomaly is detected by the engagement agent.

    Published to: agent:notifications:{event_id}

    Example:
    {
        "type": "anomaly_detected",
        "event_id": "evt_abc123",
        "timestamp": "2026-02-02T12:00:00Z",
        "session_id": "sess_xyz789",
        "anomaly_type": "ENGAGEMENT_DROP",
        "severity": "WARNING",
        "engagement_score": 0.45
    }
    """
    type: Literal["anomaly_detected"] = "anomaly_detected"
    event_id: str = Field(..., min_length=1, max_length=255)
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")
    session_id: str = Field(..., min_length=1, max_length=255)
    anomaly_type: AnomalyType
    severity: NotificationSeverity
    engagement_score: float = Field(..., ge=0.0, le=1.0)

    class Config:
        use_enum_values = True


class InterventionExecutedNotification(BaseModel):
    """
    Notification published when an intervention is executed by the engagement agent.

    Published to: agent:notifications:{event_id}

    Example:
    {
        "type": "intervention_executed",
        "event_id": "evt_abc123",
        "timestamp": "2026-02-02T12:00:00Z",
        "session_id": "sess_xyz789",
        "intervention_type": "POLL",
        "confidence": 0.85,
        "auto_approved": true
    }
    """
    type: Literal["intervention_executed"] = "intervention_executed"
    event_id: str = Field(..., min_length=1, max_length=255)
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")
    session_id: str = Field(..., min_length=1, max_length=255)
    intervention_type: InterventionType
    confidence: float = Field(..., ge=0.0, le=1.0)
    auto_approved: bool = False

    class Config:
        use_enum_values = True


AgentNotification = Union[AnomalyDetectedNotification, InterventionExecutedNotification]


# =====================
# Incoming Event Models (for receiving from Redis)
# =====================


class ChatMessageEvent(BaseModel):
    """
    Chat message event from Redis

    Example:
    {
        "sessionId": "session_123",
        "eventId": "event_456",
        "message": {...}
    }
    """
    sessionId: str = Field(..., min_length=1, max_length=255)
    eventId: str = Field(..., min_length=1, max_length=255)
    message: Dict[str, Any] = Field(default_factory=dict)

    @validator('sessionId', 'eventId')
    def validate_ids(cls, v):
        """Ensure IDs are non-empty strings"""
        if not v or not v.strip():
            raise ValueError('ID must be a non-empty string')
        return v.strip()


class PollVoteEvent(BaseModel):
    """
    Poll vote event from Redis

    Example:
    {
        "sessionId": "session_123",
        "eventId": "event_456",
        "pollId": "poll_789",
        "userId": "user_101"
    }
    """
    sessionId: str = Field(..., min_length=1, max_length=255)
    eventId: str = Field(..., min_length=1, max_length=255)
    pollId: str = Field(..., min_length=1, max_length=255)
    userId: Optional[str] = Field(None, max_length=255)

    @validator('sessionId', 'eventId', 'pollId')
    def validate_required_ids(cls, v):
        """Ensure required IDs are non-empty strings"""
        if not v or not v.strip():
            raise ValueError('ID must be a non-empty string')
        return v.strip()


class PollClosedEvent(BaseModel):
    """
    Poll closed event from Redis

    Example:
    {
        "sessionId": "session_123",
        "eventId": "event_456",
        "pollId": "poll_789"
    }
    """
    sessionId: Optional[str] = Field(None, max_length=255)
    eventId: Optional[str] = Field(None, max_length=255)
    pollId: str = Field(..., min_length=1, max_length=255)

    @validator('pollId')
    def validate_poll_id(cls, v):
        """Ensure poll ID is non-empty"""
        if not v or not v.strip():
            raise ValueError('Poll ID must be a non-empty string')
        return v.strip()


class ReactionEvent(BaseModel):
    """
    Reaction event from Redis (from platform.events.live.reaction.v1 stream)

    Example:
    {
        "userId": "user_123",
        "sessionId": "session_456",
        "emoji": "🔥",
        "timestamp": "2026-02-02T12:00:00.000Z"
    }
    """
    userId: str = Field(..., min_length=1, max_length=255)
    sessionId: str = Field(..., min_length=1, max_length=255)
    emoji: str = Field(..., min_length=1, max_length=10)
    timestamp: Optional[str] = None
    # eventId is optional - reactions may not always have it
    eventId: Optional[str] = Field(None, max_length=255)

    @validator('sessionId', 'userId')
    def validate_required_ids(cls, v):
        """Ensure required IDs are non-empty strings"""
        if not v or not v.strip():
            raise ValueError('ID must be a non-empty string')
        return v.strip()


class SyncEvent(BaseModel):
    """
    Sync event from Redis (user presence, reactions, messages, etc.)

    Examples:
    {
        "type": "user_join",
        "sessionId": "session_123",
        "eventId": "event_456",
        "userId": "user_789"
    }
    {
        "type": "reaction",
        "sessionId": "session_123",
        "eventId": "event_456"
    }
    {
        "type": "message_created",
        "sessionId": "session_123",
        "eventId": "event_456",
        "payload": {...}
    }
    """
    type: str = Field(..., min_length=1, max_length=50)
    sessionId: str = Field(..., min_length=1, max_length=255)
    eventId: str = Field(..., min_length=1, max_length=255)
    userId: Optional[str] = Field(None, max_length=255)
    data: Optional[Dict[str, Any]] = None
    payload: Optional[Dict[str, Any]] = None  # For message events

    @validator('type')
    def validate_event_type(cls, v):
        """Ensure event type is valid"""
        valid_types = {
            'user_join',
            'user_leave',
            'reaction',
            'presence_update',
            'typing',
            'emoji',
            'message_created',  # Chat message created
            'message_updated',  # Chat message edited
            'message_deleted',  # Chat message deleted
        }

        if v not in valid_types:
            # Log unknown type but don't fail validation
            # This allows for future event types without breaking
            logger.debug(f"Unknown sync event type received: {v}")

        return v

    @validator('sessionId', 'eventId')
    def validate_required_fields(cls, v):
        """Ensure required IDs are non-empty strings"""
        if not v or not v.strip():
            raise ValueError('ID must be a non-empty string')
        return v.strip()
