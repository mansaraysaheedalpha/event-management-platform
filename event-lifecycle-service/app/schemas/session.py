# app/schemas/session.py
from pydantic import BaseModel, Field, field_validator
from typing import Optional, List
from datetime import datetime
from enum import Enum
import re
from .speaker import Speaker


class SessionType(str, Enum):
    """Session type classification for virtual event support."""
    MAINSTAGE = "MAINSTAGE"
    BREAKOUT = "BREAKOUT"
    WORKSHOP = "WORKSHOP"
    NETWORKING = "NETWORKING"
    EXPO = "EXPO"


def validate_url_field(v: Optional[str]) -> Optional[str]:
    """Validate URL format for streaming and recording URLs."""
    if v is None:
        return v
    url_pattern = re.compile(
        r'^https?://'
        r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'
        r'localhost|'
        r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'
        r'(?::\d+)?'
        r'(?:/?|[/?]\S+)$', re.IGNORECASE)
    if not url_pattern.match(v):
        raise ValueError('Invalid URL format')
    return v


class Session(BaseModel):
    id: str
    event_id: str
    title: str
    start_time: datetime
    end_time: datetime
    chat_enabled: bool = True
    qa_enabled: bool = True
    polls_enabled: bool = True
    chat_open: bool = False
    qa_open: bool = False
    polls_open: bool = False
    speakers: List[Speaker] = []
    organization_id: Optional[str] = None

    # Virtual Session Support (Phase 1)
    session_type: SessionType = Field(
        SessionType.MAINSTAGE,
        description="Session type: MAINSTAGE, BREAKOUT, WORKSHOP, NETWORKING, EXPO"
    )
    virtual_room_id: Optional[str] = Field(None, description="External virtual room identifier")
    streaming_url: Optional[str] = Field(None, description="Live stream URL for virtual sessions")
    recording_url: Optional[str] = Field(None, description="Recording URL for on-demand playback")
    is_recordable: bool = Field(True, description="Whether session can be recorded")
    requires_camera: bool = Field(False, description="Whether attendees need camera access")
    requires_microphone: bool = Field(False, description="Whether attendees need microphone access")
    max_participants: Optional[int] = Field(None, ge=1, le=10000, description="Max participants for interactive sessions")
    broadcast_only: bool = Field(True, description="View-only session (no attendee A/V)")

    # Green Room / Backstage Support (P1)
    green_room_enabled: bool = Field(True, description="Enable green room for speakers")
    green_room_opens_minutes_before: int = Field(15, ge=5, le=60, description="Minutes before session green room opens")
    green_room_notes: Optional[str] = Field(None, max_length=1000, description="Producer notes visible in green room")

    model_config = {"from_attributes": True}


class SessionCreate(BaseModel):
    title: str = Field(..., json_schema_extra={"example": "The Future of LLM's"})
    start_time: datetime
    end_time: datetime
    speaker_ids: Optional[List[str]] = []
    chat_enabled: bool = True
    qa_enabled: bool = True
    polls_enabled: bool = True
    # Virtual Session Support (Phase 1)
    session_type: SessionType = SessionType.MAINSTAGE
    virtual_room_id: Optional[str] = None
    streaming_url: Optional[str] = None
    is_recordable: bool = True
    requires_camera: bool = False
    requires_microphone: bool = False
    max_participants: Optional[int] = Field(None, ge=1, le=10000)
    broadcast_only: bool = True
    # Green Room / Backstage Support (P1)
    green_room_enabled: bool = True
    green_room_opens_minutes_before: int = Field(15, ge=5, le=60)
    green_room_notes: Optional[str] = Field(None, max_length=1000)

    @field_validator('streaming_url')
    @classmethod
    def validate_streaming_url(cls, v: Optional[str]) -> Optional[str]:
        return validate_url_field(v)


class SessionUpdate(BaseModel):
    title: Optional[str] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    speaker_ids: Optional[List[str]] = None
    chat_enabled: Optional[bool] = None
    qa_enabled: Optional[bool] = None
    polls_enabled: Optional[bool] = None
    chat_open: Optional[bool] = None
    qa_open: Optional[bool] = None
    polls_open: Optional[bool] = None
    # Virtual Session Support (Phase 1)
    session_type: Optional[SessionType] = None
    virtual_room_id: Optional[str] = None
    streaming_url: Optional[str] = None
    recording_url: Optional[str] = None
    is_recordable: Optional[bool] = None
    requires_camera: Optional[bool] = None
    requires_microphone: Optional[bool] = None
    max_participants: Optional[int] = Field(None, ge=1, le=10000)
    broadcast_only: Optional[bool] = None
    # Green Room / Backstage Support (P1)
    green_room_enabled: Optional[bool] = None
    green_room_opens_minutes_before: Optional[int] = Field(None, ge=5, le=60)
    green_room_notes: Optional[str] = Field(None, max_length=1000)

    @field_validator('streaming_url', 'recording_url')
    @classmethod
    def validate_urls(cls, v: Optional[str]) -> Optional[str]:
        return validate_url_field(v)
