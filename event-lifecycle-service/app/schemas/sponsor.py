# app/schemas/sponsor.py
"""
Pydantic schemas for sponsor management.
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, EmailStr, Field, HttpUrl


# ============================================
# Sponsor Tier Schemas
# ============================================

class SponsorTierBase(BaseModel):
    name: str = Field(..., max_length=100)
    display_order: int = Field(default=0)
    color: Optional[str] = Field(None, max_length=7, pattern=r'^#[0-9A-Fa-f]{6}$')
    benefits: List[str] = Field(default_factory=list)
    booth_size: Optional[str] = Field(None, max_length=20)
    logo_placement: Optional[str] = Field(None, max_length=50)
    max_representatives: int = Field(default=3, ge=1, le=50)
    can_capture_leads: bool = Field(default=True)
    can_export_leads: bool = Field(default=True)
    can_send_messages: bool = Field(default=False)
    price_cents: Optional[int] = Field(None, ge=0)
    currency: Optional[str] = Field(default="USD", max_length=3)


class SponsorTierCreate(SponsorTierBase):
    pass


class SponsorTierUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=100)
    display_order: Optional[int] = None
    color: Optional[str] = Field(None, max_length=7)
    benefits: Optional[List[str]] = None
    booth_size: Optional[str] = Field(None, max_length=20)
    logo_placement: Optional[str] = Field(None, max_length=50)
    max_representatives: Optional[int] = Field(None, ge=1, le=50)
    can_capture_leads: Optional[bool] = None
    can_export_leads: Optional[bool] = None
    can_send_messages: Optional[bool] = None
    price_cents: Optional[int] = Field(None, ge=0)
    currency: Optional[str] = Field(None, max_length=3)
    is_active: Optional[bool] = None


class SponsorTierResponse(SponsorTierBase):
    id: str
    organization_id: str
    event_id: str
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ============================================
# Sponsor Schemas
# ============================================

class SponsorBase(BaseModel):
    company_name: str = Field(..., max_length=200)
    company_description: Optional[str] = None
    company_website: Optional[str] = Field(None, max_length=500)
    company_logo_url: Optional[str] = Field(None, max_length=500)
    contact_name: Optional[str] = Field(None, max_length=200)
    contact_email: Optional[EmailStr] = None
    contact_phone: Optional[str] = Field(None, max_length=50)
    booth_number: Optional[str] = Field(None, max_length=50)
    booth_description: Optional[str] = None
    custom_booth_url: Optional[str] = Field(None, max_length=500)
    social_links: Optional[Dict[str, str]] = Field(default_factory=dict)
    marketing_assets: Optional[List[Dict[str, Any]]] = Field(default_factory=list)
    lead_capture_enabled: bool = Field(default=True)
    lead_notification_email: Optional[EmailStr] = None
    custom_fields: Optional[Dict[str, Any]] = Field(default_factory=dict)


class SponsorCreate(SponsorBase):
    tier_id: Optional[str] = None


class SponsorUpdate(BaseModel):
    tier_id: Optional[str] = None
    company_name: Optional[str] = Field(None, max_length=200)
    company_description: Optional[str] = None
    company_website: Optional[str] = Field(None, max_length=500)
    company_logo_url: Optional[str] = Field(None, max_length=500)
    contact_name: Optional[str] = Field(None, max_length=200)
    contact_email: Optional[EmailStr] = None
    contact_phone: Optional[str] = Field(None, max_length=50)
    booth_number: Optional[str] = Field(None, max_length=50)
    booth_description: Optional[str] = None
    custom_booth_url: Optional[str] = Field(None, max_length=500)
    social_links: Optional[Dict[str, str]] = None
    marketing_assets: Optional[List[Dict[str, Any]]] = None
    lead_capture_enabled: Optional[bool] = None
    lead_notification_email: Optional[EmailStr] = None
    custom_fields: Optional[Dict[str, Any]] = None
    is_active: Optional[bool] = None
    is_featured: Optional[bool] = None


class SponsorBoothSettingsUpdate(BaseModel):
    """Schema for sponsor representatives to update their own booth settings."""
    company_description: Optional[str] = None
    company_website: Optional[str] = Field(None, max_length=500)
    booth_number: Optional[str] = Field(None, max_length=50)
    booth_description: Optional[str] = None
    social_links: Optional[Dict[str, str]] = None
    lead_capture_enabled: Optional[bool] = None
    lead_notification_email: Optional[EmailStr] = None


class SponsorResponse(SponsorBase):
    id: str
    organization_id: str
    event_id: str
    tier_id: Optional[str]
    is_active: bool
    is_featured: bool
    is_archived: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class SponsorWithTierResponse(SponsorResponse):
    tier: Optional[SponsorTierResponse] = None


# ============================================
# Sponsor User Schemas
# ============================================

class SponsorUserBase(BaseModel):
    role: str = Field(default="representative", pattern=r'^(admin|representative|booth_staff|viewer)$')
    can_view_leads: bool = Field(default=True)
    can_export_leads: bool = Field(default=False)
    can_message_attendees: bool = Field(default=False)
    can_manage_booth: bool = Field(default=False)
    can_invite_others: bool = Field(default=False)


class SponsorUserCreate(SponsorUserBase):
    user_id: str


class SponsorUserUpdate(BaseModel):
    role: Optional[str] = Field(None, pattern=r'^(admin|representative|booth_staff|viewer)$')
    can_view_leads: Optional[bool] = None
    can_export_leads: Optional[bool] = None
    can_message_attendees: Optional[bool] = None
    can_manage_booth: Optional[bool] = None
    can_invite_others: Optional[bool] = None
    is_active: Optional[bool] = None


class SponsorUserResponse(SponsorUserBase):
    id: str
    sponsor_id: str
    user_id: str
    is_active: bool
    joined_at: datetime
    last_active_at: Optional[datetime]

    class Config:
        from_attributes = True


# ============================================
# Sponsor Invitation Schemas
# ============================================

class SponsorInvitationCreate(BaseModel):
    email: EmailStr
    role: str = Field(default="representative", pattern=r'^(admin|representative|booth_staff|viewer)$')
    can_view_leads: bool = Field(default=True)
    can_export_leads: bool = Field(default=False)
    can_message_attendees: bool = Field(default=False)
    can_manage_booth: bool = Field(default=False)
    can_invite_others: bool = Field(default=False)
    personal_message: Optional[str] = Field(None, max_length=500)


class SponsorInvitationResponse(BaseModel):
    id: str
    sponsor_id: str
    email: str
    role: str
    status: str
    can_view_leads: bool
    can_export_leads: bool
    can_message_attendees: bool
    can_manage_booth: bool
    can_invite_others: bool
    personal_message: Optional[str]
    invited_by_user_id: str
    accepted_by_user_id: Optional[str]
    accepted_at: Optional[datetime]
    expires_at: datetime
    created_at: datetime

    class Config:
        from_attributes = True


class AcceptInvitationRequest(BaseModel):
    token: str


class SponsorInvitationPreviewResponse(BaseModel):
    """Response for sponsor invitation preview (public endpoint)."""
    email: str
    sponsor_name: str
    sponsor_logo_url: Optional[str] = None
    inviter_name: str
    role_name: str
    user_exists: bool
    existing_user_first_name: Optional[str] = None
    expires_at: datetime


class AcceptInvitationNewUserRequest(BaseModel):
    """Request to accept invitation as a new user (no existing account)."""
    token: str
    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)
    password: str = Field(..., min_length=8, max_length=128)


class AcceptInvitationExistingUserRequest(BaseModel):
    """Request to accept invitation as an existing user."""
    token: str
    password: str = Field(..., min_length=1)


class AcceptInvitationResponse(BaseModel):
    """Response after successfully accepting a sponsor invitation."""
    message: str
    sponsor_id: str
    sponsor_name: str
    event_id: str
    role: str
    user: dict
    access_token: str


# ============================================
# Sponsor Lead Schemas
# ============================================

class SponsorLeadInteraction(BaseModel):
    type: str  # booth_visit, content_download, demo_request, etc.
    timestamp: datetime
    duration_seconds: Optional[int] = None
    content_name: Optional[str] = None
    notes: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class SponsorLeadCreate(BaseModel):
    user_id: str
    user_name: Optional[str] = None
    user_email: Optional[EmailStr] = None
    user_company: Optional[str] = None
    user_title: Optional[str] = None
    interaction_type: str  # Initial interaction type
    interaction_metadata: Optional[Dict[str, Any]] = None


class SponsorLeadUpdate(BaseModel):
    follow_up_status: Optional[str] = Field(
        None, pattern=r'^(new|contacted|qualified|not_interested|converted)$'
    )
    follow_up_notes: Optional[str] = None
    tags: Optional[List[str]] = None
    is_starred: Optional[bool] = None
    contact_notes: Optional[str] = None


class SponsorLeadResponse(BaseModel):
    id: str
    sponsor_id: str
    event_id: str
    user_id: str
    user_name: Optional[str]
    user_email: Optional[str]
    user_company: Optional[str]
    user_title: Optional[str]
    intent_score: int
    intent_level: str
    first_interaction_at: datetime
    last_interaction_at: datetime
    interaction_count: int
    interactions: List[Dict[str, Any]]
    contact_requested: bool
    contact_notes: Optional[str]
    preferred_contact_method: Optional[str]
    follow_up_status: str
    follow_up_notes: Optional[str]
    followed_up_at: Optional[datetime]
    followed_up_by_user_id: Optional[str]
    tags: List[str]
    is_starred: bool
    is_archived: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ============================================
# Analytics/Stats Schemas
# ============================================

class SponsorStats(BaseModel):
    total_leads: int
    hot_leads: int
    warm_leads: int
    cold_leads: int
    leads_contacted: int
    leads_converted: int
    conversion_rate: float
    avg_intent_score: float


class SponsorLeadExport(BaseModel):
    """Schema for exporting leads to CSV/Excel"""
    name: str
    email: str
    company: Optional[str]
    title: Optional[str]
    intent_level: str
    intent_score: int
    first_interaction: datetime
    last_interaction: datetime
    interaction_count: int
    contact_requested: bool
    follow_up_status: str
    tags: str  # Comma-separated


# ============================================
# Internal API Schemas
# ============================================

class SponsorSummary(BaseModel):
    """Summary of a sponsor for status checks."""
    id: str
    event_id: str
    company_name: str
    role: Optional[str] = None  # User's role in this sponsor


class UserSponsorStatusResponse(BaseModel):
    """Response for checking if a user is a sponsor representative."""
    is_sponsor: bool
    sponsor_count: int
    sponsors: List[SponsorSummary]
