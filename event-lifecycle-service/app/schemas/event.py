# app/schemas/event.py
from pydantic import BaseModel, Field, field_validator
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
from enum import Enum
import re


class EventStatus(str, Enum):
    draft = "draft"
    published = "published"
    archived = "archived"


class EventType(str, Enum):
    """Event type classification for virtual event support."""
    IN_PERSON = "IN_PERSON"
    VIRTUAL = "VIRTUAL"
    HYBRID = "HYBRID"


class StreamingProvider(str, Enum):
    """Supported streaming providers."""
    MUX = "mux"
    IVS = "ivs"
    CLOUDFLARE = "cloudflare"
    YOUTUBE = "youtube"
    VIMEO = "vimeo"
    RTMP = "rtmp"
    DAILY = "daily"


class VirtualSettings(BaseModel):
    """Virtual event configuration settings."""
    streaming_provider: Optional[StreamingProvider] = Field(
        None, description="Streaming provider (mux, ivs, cloudflare, youtube, vimeo, rtmp)"
    )
    streaming_url: Optional[str] = Field(None, description="Stream embed URL")
    recording_enabled: bool = Field(True, description="Enable session recording")
    auto_captions: bool = Field(False, description="Enable AI-generated captions")
    timezone_display: Optional[str] = Field(None, description="Display timezone for attendees")
    lobby_enabled: bool = Field(False, description="Show lobby before event starts")
    lobby_video_url: Optional[str] = Field(None, description="Video to play in lobby")
    max_concurrent_viewers: Optional[int] = Field(None, ge=1, le=1000000, description="Max concurrent viewers limit")
    geo_restrictions: Optional[List[str]] = Field(None, description="ISO country codes to allow/block")

    @field_validator('streaming_url', 'lobby_video_url')
    @classmethod
    def validate_url(cls, v: Optional[str]) -> Optional[str]:
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

    model_config = {"from_attributes": True}


class Event(BaseModel):
    id: str = Field(..., json_schema_extra={"example": "evt_c5a6d8e0f9b1"})
    organization_id: str = Field(..., json_schema_extra={"example": "org_a1b2c3d4e5"})
    name: str = Field(..., json_schema_extra={"example": "Global AI Summit"})
    version: int = Field(
        ..., description="The current version number of the event state"
    )
    description: Optional[str] = Field(
        None, json_schema_extra={"example": "The premier event for AI enthusiasts"}
    )
    status: EventStatus = Field(..., json_schema_extra={"example": "published"})
    start_date: datetime
    end_date: datetime
    venue_id: Optional[str] = Field(
        None, json_schema_extra={"example": "ven_f9e8d7c6b5"}
    )
    is_public: bool = Field(
        False, description="Indicates if the event is publicly discoverable."
    )
    is_archived: bool = Field(
        False, description="Indicates if an event is deleted or not"
    )
    createdAt: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updatedAt: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    # Virtual Event Support (Phase 1)
    event_type: EventType = Field(
        EventType.IN_PERSON,
        description="Event type: IN_PERSON, VIRTUAL, or HYBRID"
    )
    virtual_settings: Optional[Dict[str, Any]] = Field(
        None, description="Virtual event configuration"
    )

    model_config = {"from_attributes": True}


class EventCreate(BaseModel):
    owner_id: str
    name: str = Field(..., json_schema_extra={"example": "Global AI Summit"})
    description: Optional[str] = Field(
        None, json_schema_extra={"example": "The premier event for AI enthusiasts."}
    )
    start_date: datetime
    end_date: datetime
    venue_id: Optional[str] = Field(
        None, json_schema_extra={"example": "ven_f9e8d7c6b5"}
    )
    imageUrl: Optional[str] = None
    # Virtual Event Support (Phase 1)
    event_type: EventType = Field(
        EventType.IN_PERSON,
        description="Event type: IN_PERSON, VIRTUAL, or HYBRID"
    )
    virtual_settings: Optional[Dict[str, Any]] = Field(
        None, description="Virtual event configuration"
    )


# NEW: Helper schema for pagination details
class Pagination(BaseModel):
    totalItems: int
    totalPages: int
    currentPage: int


# NEW: The full response model for the list endpoint
class PaginatedEvent(BaseModel):
    data: List[Event]
    pagination: Pagination


# NEW: Schema for updating an event. All fields are optional.
class EventUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    venue_id: Optional[str] = None
    is_public: Optional[bool] = None
    imageUrl: Optional[str] = None
    # Virtual Event Support (Phase 1)
    event_type: Optional[EventType] = None
    virtual_settings: Optional[Dict[str, Any]] = None


# ✅ --- NEW SCHEMAS FOR IMAGE UPLOAD ---
class ImageUploadRequest(BaseModel):
    content_type: str
    filename: str


class ImageUploadResponse(BaseModel):
    url: str
    fields: dict
    s3_key: str
