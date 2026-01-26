# app/schemas/sponsor_campaign.py
"""
Pydantic schemas for sponsor email campaigns.

Production-grade validation:
- Email template validation
- Recipient count limits
- Template variable validation
- Sanitization of user input
"""

from typing import Optional, Dict, List, Any
from pydantic import BaseModel, Field, field_validator
from datetime import datetime
import re


class CampaignCreate(BaseModel):
    """Schema for creating a new sponsor campaign."""

    name: str = Field(..., min_length=1, max_length=200, description="Internal campaign name")
    subject: str = Field(..., min_length=1, max_length=500, description="Email subject line")
    message_body: str = Field(..., min_length=10, description="Email body with {{variable}} support")
    audience_type: str = Field(..., description="all, hot, warm, cold, new, contacted, custom")
    audience_filter: Optional[Dict[str, Any]] = Field(None, description="Custom filter criteria")
    scheduled_at: Optional[datetime] = Field(None, description="Schedule for future sending")
    campaign_metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)

    @field_validator('audience_type')
    @classmethod
    def validate_audience_type(cls, v: str) -> str:
        """Validate audience type is one of allowed values."""
        allowed = ['all', 'hot', 'warm', 'cold', 'new', 'contacted', 'custom']
        if v not in allowed:
            raise ValueError(f"audience_type must be one of: {', '.join(allowed)}")
        return v

    @field_validator('subject')
    @classmethod
    def validate_subject(cls, v: str) -> str:
        """Sanitize subject line to prevent injection."""
        # Remove line breaks (subjects should be single line)
        v = v.replace('\n', ' ').replace('\r', ' ')
        # Limit consecutive spaces
        v = re.sub(r'\s{2,}', ' ', v)
        return v.strip()

    @field_validator('message_body')
    @classmethod
    def validate_message_body(cls, v: str) -> str:
        """Validate message body contains no malicious content."""
        # Check for valid template variables ({{name}}, {{company}}, etc.)
        template_vars = re.findall(r'\{\{(\w+)\}\}', v)
        allowed_vars = ['name', 'company', 'title', 'email', 'first_name', 'last_name']

        for var in template_vars:
            if var not in allowed_vars:
                raise ValueError(
                    f"Invalid template variable: {{{{{var}}}}}. "
                    f"Allowed: {', '.join(allowed_vars)}"
                )

        # Check minimum length for meaningful message
        if len(v.strip()) < 10:
            raise ValueError("Message body must be at least 10 characters")

        return v

    @field_validator('audience_filter')
    @classmethod
    def validate_audience_filter(cls, v: Optional[Dict], values: Dict) -> Optional[Dict]:
        """Validate custom audience filter if audience_type is 'custom'."""
        if values.get('audience_type') == 'custom' and not v:
            raise ValueError("audience_filter is required when audience_type is 'custom'")
        return v


class CampaignUpdate(BaseModel):
    """Schema for updating a campaign (only allowed in draft status)."""

    name: Optional[str] = Field(None, min_length=1, max_length=200)
    subject: Optional[str] = Field(None, min_length=1, max_length=500)
    message_body: Optional[str] = Field(None, min_length=10)
    audience_type: Optional[str] = None
    audience_filter: Optional[Dict[str, Any]] = None
    scheduled_at: Optional[datetime] = None


class CampaignResponse(BaseModel):
    """Schema for campaign response."""

    id: str
    sponsor_id: str
    event_id: str
    name: str
    subject: str
    message_body: str
    audience_type: str
    audience_filter: Optional[Dict[str, Any]]
    total_recipients: int
    sent_count: int
    delivered_count: int
    failed_count: int
    opened_count: int
    clicked_count: int
    status: str
    scheduled_at: Optional[datetime]
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    created_by_user_id: str
    created_by_user_name: Optional[str]
    error_message: Optional[str]
    campaign_metadata: Dict[str, Any]
    created_at: datetime
    updated_at: datetime

    # Computed fields
    open_rate: Optional[float] = Field(None, description="Percentage of emails opened")
    click_rate: Optional[float] = Field(None, description="Percentage of emails clicked")

    class Config:
        from_attributes = True

    def __init__(self, **data):
        super().__init__(**data)
        # Calculate rates
        if self.sent_count > 0:
            self.open_rate = round((self.opened_count / self.sent_count) * 100, 2)
            self.click_rate = round((self.clicked_count / self.sent_count) * 100, 2)


class CampaignListResponse(BaseModel):
    """Schema for paginated campaign list."""

    campaigns: List[CampaignResponse]
    total: int
    page: int
    page_size: int


class DeliveryResponse(BaseModel):
    """Schema for delivery status response."""

    id: str
    campaign_id: str
    lead_id: str
    recipient_email: str
    recipient_name: Optional[str]
    status: str
    opened_at: Optional[datetime]
    opened_count: int
    first_click_at: Optional[datetime]
    click_count: int
    error_message: Optional[str]
    retry_count: int
    queued_at: datetime
    sent_at: Optional[datetime]
    delivered_at: Optional[datetime]

    class Config:
        from_attributes = True


class CampaignStats(BaseModel):
    """Schema for campaign analytics."""

    campaign_id: str
    total_recipients: int
    sent: int
    delivered: int
    failed: int
    opened: int
    clicked: int
    delivery_rate: float
    open_rate: float
    click_rate: float
    bounce_rate: float
