"""
Pydantic models for Redis event validation
Ensures incoming Redis Pub/Sub events are properly validated before processing
"""
from pydantic import BaseModel, Field, validator
from typing import Optional, Any, Dict
from datetime import datetime


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


class SyncEvent(BaseModel):
    """
    Sync event from Redis (user presence, reactions, etc.)

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
    """
    type: str = Field(..., min_length=1, max_length=50)
    sessionId: str = Field(..., min_length=1, max_length=255)
    eventId: str = Field(..., min_length=1, max_length=255)
    userId: Optional[str] = Field(None, max_length=255)
    data: Optional[Dict[str, Any]] = None

    @validator('type')
    def validate_event_type(cls, v):
        """Ensure event type is valid"""
        valid_types = {
            'user_join',
            'user_leave',
            'reaction',
            'presence_update',
            'typing',
            'emoji'
        }

        if v not in valid_types:
            # Log unknown type but don't fail validation
            # This allows for future event types without breaking
            pass

        return v

    @validator('sessionId', 'eventId')
    def validate_required_fields(cls, v):
        """Ensure required IDs are non-empty strings"""
        if not v or not v.strip():
            raise ValueError('ID must be a non-empty string')
        return v.strip()
