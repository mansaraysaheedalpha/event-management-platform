# app/schemas/ab_test.py
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, field_validator
from datetime import datetime
from enum import Enum
import re


class GoalMetric(str, Enum):
    click_through = "click_through"
    purchase_conversion = "purchase_conversion"
    signup_conversion = "signup_conversion"
    engagement_time = "engagement_time"
    custom = "custom"


class ABTestVariant(BaseModel):
    id: str = Field(..., min_length=1, max_length=100, description="Unique variant identifier")
    name: str = Field(..., min_length=1, max_length=255, description="Human-readable variant name")
    weight: int = Field(default=1, ge=1, le=100, description="Relative weight for distribution")


class ABTestCreate(BaseModel):
    test_id: str = Field(
        ...,
        min_length=1,
        max_length=100,
        pattern=r"^[a-z0-9_]+$",
        description="Unique test identifier (lowercase, numbers, underscores only)"
    )
    name: str = Field(..., min_length=1, max_length=255, description="Human-readable test name")
    description: Optional[str] = Field(None, max_length=1000)
    event_id: str = Field(..., min_length=1, max_length=100, description="Event ID this test applies to")
    variants: List[ABTestVariant] = Field(..., min_items=2, description="Test variants (minimum 2)")
    goal_metric: GoalMetric = Field(..., description="Primary metric to measure")
    secondary_metrics: Optional[List[str]] = None
    target_audience: Optional[Dict[str, Any]] = None
    min_sample_size: int = Field(default=100, ge=10, le=10000, description="Minimum sample size before declaring winner")


class ABTestUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None
    variants: Optional[List[ABTestVariant]] = None
    goal_metric: Optional[GoalMetric] = None
    secondary_metrics: Optional[List[str]] = None
    target_audience: Optional[Dict[str, Any]] = None
    min_sample_size: Optional[int] = None


class ABTestResponse(BaseModel):
    id: str
    test_id: str
    name: str
    description: Optional[str]
    event_id: str
    variants: List[Dict[str, Any]]
    is_active: bool
    goal_metric: str
    secondary_metrics: Optional[List[str]]
    target_audience: Optional[Dict[str, Any]]
    min_sample_size: int
    created_at: datetime
    updated_at: datetime
    started_at: Optional[datetime]
    ended_at: Optional[datetime]

    class Config:
        from_attributes = True


class ABTestEventCreate(BaseModel):
    test_id: str = Field(..., min_length=1, max_length=100, description="Test identifier")
    event_id: str = Field(..., min_length=1, max_length=100, description="Event ID")
    session_token: str = Field(..., min_length=1, max_length=255, description="Frontend session identifier")
    variant_id: str = Field(..., min_length=1, max_length=100, description="Variant shown to user")
    event_type: str = Field(..., description="Event type: variant_view, goal_conversion, secondary_metric")
    goal_achieved: bool = Field(default=False)
    goal_value: Optional[int] = Field(None, ge=0, le=1000000000)
    user_id: Optional[str] = Field(None, max_length=255)
    user_agent: Optional[str] = Field(None, max_length=500)
    context: Optional[Dict[str, Any]] = None

    @field_validator('session_token')
    @classmethod
    def validate_session_token(cls, v: str) -> str:
        """Validate session token format"""
        if not re.match(r'^[a-zA-Z0-9_-]+$', v):
            raise ValueError('Invalid session token format. Only alphanumeric, underscore, and hyphen allowed.')
        return v

    @field_validator('user_agent')
    @classmethod
    def sanitize_user_agent(cls, v: Optional[str]) -> Optional[str]:
        """Sanitize user agent string"""
        if v:
            # Strip control characters and truncate
            v = ''.join(char for char in v if ord(char) >= 32)
            return v[:500]
        return v


class BatchABTestEventCreate(BaseModel):
    events: List[ABTestEventCreate] = Field(..., max_items=100)


class ABTestVariantStats(BaseModel):
    variant_id: str
    variant_name: str
    impressions: int
    conversions: int
    conversion_rate: float
    average_value: float
    confidence_level: float


class ABTestResults(BaseModel):
    test_id: str
    test_name: str
    is_active: bool
    total_impressions: int
    total_conversions: int
    variants: List[ABTestVariantStats]
    winner: Optional[str] = None
    confidence: Optional[float] = None
    recommendation: str
    started_at: Optional[datetime]
    ended_at: Optional[datetime]


class ABTestListItem(BaseModel):
    id: str
    test_id: str
    name: str
    event_id: str
    is_active: bool
    variants_count: int
    total_impressions: int
    created_at: datetime

    class Config:
        from_attributes = True
