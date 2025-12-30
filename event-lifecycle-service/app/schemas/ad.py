# app/schemas/ad.py
from pydantic import BaseModel, Field
from typing import Optional, List, Dict
from datetime import datetime
from enum import Enum


class ContentType(str, Enum):
    BANNER = "BANNER"
    VIDEO = "VIDEO"
    SPONSORED_SESSION = "SPONSORED_SESSION"
    INTERSTITIAL = "INTERSTITIAL"


class EventType(str, Enum):
    IMPRESSION = "IMPRESSION"
    CLICK = "CLICK"


# ==================== Ad DTOs ====================

class AdCreateDTO(BaseModel):
    event_id: str
    name: str = Field(..., min_length=1, max_length=255, json_schema_extra={"example": "Homepage Banner Q3"})
    content_type: ContentType = Field(..., json_schema_extra={"example": "BANNER"})
    media_url: str = Field(..., json_schema_extra={"example": "https://example.com/ads/banner.jpg"})
    click_url: str = Field(..., json_schema_extra={"example": "https://example.com/product"})
    display_duration_seconds: int = Field(30, gt=0, json_schema_extra={"example": 30})
    aspect_ratio: str = Field("16:9", json_schema_extra={"example": "16:9"})
    placements: List[str] = Field(default=["EVENT_HERO"], json_schema_extra={"example": ["EVENT_HERO", "SIDEBAR"]})
    target_sessions: List[str] = Field(default=[], json_schema_extra={"example": []})
    weight: int = Field(1, gt=0, json_schema_extra={"example": 1})
    frequency_cap: int = Field(3, gt=0, json_schema_extra={"example": 3})
    starts_at: Optional[datetime] = None
    ends_at: Optional[datetime] = None


class AdUpdateDTO(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    content_type: Optional[ContentType] = None
    media_url: Optional[str] = None
    click_url: Optional[str] = None
    display_duration_seconds: Optional[int] = Field(None, gt=0)
    aspect_ratio: Optional[str] = None
    placements: Optional[List[str]] = None
    target_sessions: Optional[List[str]] = None
    weight: Optional[int] = Field(None, gt=0)
    frequency_cap: Optional[int] = Field(None, gt=0)
    is_active: Optional[bool] = None
    starts_at: Optional[datetime] = None
    ends_at: Optional[datetime] = None


class AdAnalytics(BaseModel):
    impressions: int = 0
    viewable_impressions: int = 0
    clicks: int = 0
    ctr: float = 0.0
    unique_users: int = 0


class AdResponse(BaseModel):
    id: str
    event_id: str
    organization_id: str
    name: str
    content_type: str
    media_url: str
    click_url: str
    display_duration_seconds: int
    aspect_ratio: str
    placements: List[str]
    target_sessions: List[str]
    weight: int
    frequency_cap: int
    is_active: bool
    is_archived: bool
    starts_at: datetime
    ends_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime
    analytics: Optional[AdAnalytics] = None

    model_config = {"from_attributes": True}


# ==================== Ad Event DTOs ====================

class ImpressionTrackingDTO(BaseModel):
    ad_id: str
    context: Optional[str] = None
    viewable_duration_ms: int = Field(..., ge=0)
    viewport_percentage: int = Field(..., ge=0, le=100)


class BatchImpressionDTO(BaseModel):
    impressions: List[ImpressionTrackingDTO]


class ClickTrackingResponse(BaseModel):
    redirect_url: str
    open_in_new_tab: bool = True


# ==================== Analytics DTOs ====================

class DailyAdAnalytics(BaseModel):
    date: str
    impressions: int
    viewable_impressions: int
    clicks: int
    ctr: float
    unique_users: int


class AdAnalyticsResponse(BaseModel):
    ad_id: str
    ad_name: str
    total_impressions: int
    viewable_impressions: int
    total_clicks: int
    ctr: float
    unique_users: int
    daily_breakdown: List[DailyAdAnalytics]


class TopPerformer(BaseModel):
    ad_id: str
    name: str
    impressions: int
    clicks: int
    ctr: float


class PlacementAnalytics(BaseModel):
    impressions: int
    clicks: int
    ctr: float


class EventAdAnalyticsResponse(BaseModel):
    total_impressions: int
    total_clicks: int
    average_ctr: float
    top_performers: List[TopPerformer]
    by_placement: Dict[str, PlacementAnalytics]


# Backward compatibility - keep old schema names
class AdBase(BaseModel):
    name: str = Field(..., json_schema_extra={"example": "Homepage Banner Q3"})
    event_id: Optional[str] = Field(None, json_schema_extra={"example": "evt_abc"})
    content_type: str = Field(..., json_schema_extra={"example": "BANNER"})
    media_url: str = Field(
        ..., json_schema_extra={"example": "https://example.com/ads/banner.jpg"}
    )
    click_url: str = Field(
        ..., json_schema_extra={"example": "https://example.com/product"}
    )


class AdCreate(AdBase):
    pass


class AdUpdate(BaseModel):
    name: Optional[str] = None
    event_id: Optional[str] = None
    content_type: Optional[str] = None
    media_url: Optional[str] = None
    click_url: Optional[str] = None


class Ad(AdBase):
    id: str
    organization_id: str
    is_archived: bool

    model_config = {"from_attributes": True}
