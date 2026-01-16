# app/graphql/sponsor_types.py
"""
GraphQL types for sponsor management.
"""

import strawberry
from typing import Optional, List
from datetime import datetime
import json


# ============================================
# Sponsor Tier Types
# ============================================

@strawberry.type
class SponsorTierType:
    id: str
    organization_id: str
    event_id: str
    name: str
    display_order: int
    color: Optional[str]
    booth_size: Optional[str]
    logo_placement: Optional[str]
    max_representatives: int
    can_capture_leads: bool
    can_export_leads: bool
    can_send_messages: bool
    price_cents: Optional[int]
    currency: Optional[str]
    is_active: bool
    created_at: datetime
    updated_at: datetime

    @strawberry.field
    def benefits(self, root) -> List[str]:
        """Return benefits list."""
        benefits_data = getattr(root, 'benefits', None)
        if benefits_data is None:
            return []
        if isinstance(benefits_data, list):
            return benefits_data
        if isinstance(benefits_data, str):
            try:
                return json.loads(benefits_data)
            except:
                return []
        return []


# ============================================
# Sponsor Types
# ============================================

@strawberry.type
class SponsorType:
    id: str
    organization_id: str
    event_id: str
    tier_id: Optional[str]
    company_name: str
    company_description: Optional[str]
    company_website: Optional[str]
    company_logo_url: Optional[str]
    contact_name: Optional[str]
    contact_email: Optional[str]
    contact_phone: Optional[str]
    booth_number: Optional[str]
    booth_description: Optional[str]
    custom_booth_url: Optional[str]
    lead_capture_enabled: bool
    lead_notification_email: Optional[str]
    is_active: bool
    is_featured: bool
    is_archived: bool
    created_at: datetime
    updated_at: datetime

    @strawberry.field
    def social_links(self, root) -> Optional[str]:
        """Return social links as JSON string."""
        data = getattr(root, 'social_links', None)
        if data is None:
            return None
        if isinstance(data, dict):
            return json.dumps(data)
        if isinstance(data, str):
            return data
        return None

    @strawberry.field
    def marketing_assets(self, root) -> Optional[str]:
        """Return marketing assets as JSON string."""
        data = getattr(root, 'marketing_assets', None)
        if data is None:
            return None
        if isinstance(data, list):
            return json.dumps(data)
        if isinstance(data, str):
            return data
        return None

    @strawberry.field
    def custom_fields(self, root) -> Optional[str]:
        """Return custom fields as JSON string."""
        data = getattr(root, 'custom_fields', None)
        if data is None:
            return None
        if isinstance(data, dict):
            return json.dumps(data)
        if isinstance(data, str):
            return data
        return None


@strawberry.type
class SponsorWithTierType:
    id: str
    organization_id: str
    event_id: str
    tier_id: Optional[str]
    company_name: str
    company_description: Optional[str]
    company_website: Optional[str]
    company_logo_url: Optional[str]
    contact_name: Optional[str]
    contact_email: Optional[str]
    contact_phone: Optional[str]
    booth_number: Optional[str]
    booth_description: Optional[str]
    custom_booth_url: Optional[str]
    lead_capture_enabled: bool
    lead_notification_email: Optional[str]
    is_active: bool
    is_featured: bool
    is_archived: bool
    created_at: datetime
    updated_at: datetime
    tier: Optional[SponsorTierType]


# ============================================
# Sponsor User Types
# ============================================

@strawberry.type
class SponsorUserType:
    id: str
    sponsor_id: str
    user_id: str
    role: str
    can_view_leads: bool
    can_export_leads: bool
    can_message_attendees: bool
    can_manage_booth: bool
    can_invite_others: bool
    is_active: bool
    joined_at: datetime
    last_active_at: Optional[datetime]


# ============================================
# Sponsor Invitation Types
# ============================================

@strawberry.type
class SponsorInvitationType:
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


# ============================================
# Sponsor Lead Types
# ============================================

@strawberry.type
class SponsorLeadInteractionType:
    type: str
    timestamp: datetime
    duration_seconds: Optional[int]
    content_name: Optional[str]
    notes: Optional[str]


@strawberry.type
class SponsorLeadType:
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
    contact_requested: bool
    contact_notes: Optional[str]
    preferred_contact_method: Optional[str]
    follow_up_status: str
    follow_up_notes: Optional[str]
    followed_up_at: Optional[datetime]
    followed_up_by_user_id: Optional[str]
    is_starred: bool
    is_archived: bool
    created_at: datetime
    updated_at: datetime

    @strawberry.field
    def interactions(self, root) -> Optional[str]:
        """Return interactions as JSON string."""
        data = getattr(root, 'interactions', None)
        if data is None:
            return None
        if isinstance(data, list):
            return json.dumps(data)
        if isinstance(data, str):
            return data
        return None

    @strawberry.field
    def tags(self, root) -> List[str]:
        """Return tags list."""
        tags_data = getattr(root, 'tags', None)
        if tags_data is None:
            return []
        if isinstance(tags_data, list):
            return tags_data
        if isinstance(tags_data, str):
            try:
                return json.loads(tags_data)
            except:
                return []
        return []


# ============================================
# Stats Types
# ============================================

@strawberry.type
class SponsorStatsType:
    total_leads: int
    hot_leads: int
    warm_leads: int
    cold_leads: int
    leads_contacted: int
    leads_converted: int
    conversion_rate: float
    avg_intent_score: float


# ============================================
# Input Types
# ============================================

@strawberry.input
class SponsorTierCreateInput:
    name: str
    display_order: int = 0
    color: Optional[str] = None
    benefits: Optional[List[str]] = None
    booth_size: Optional[str] = None
    logo_placement: Optional[str] = None
    max_representatives: int = 3
    can_capture_leads: bool = True
    can_export_leads: bool = True
    can_send_messages: bool = False
    price_cents: Optional[int] = None
    currency: str = "USD"


@strawberry.input
class SponsorTierUpdateInput:
    name: Optional[str] = None
    display_order: Optional[int] = None
    color: Optional[str] = None
    benefits: Optional[List[str]] = None
    booth_size: Optional[str] = None
    logo_placement: Optional[str] = None
    max_representatives: Optional[int] = None
    can_capture_leads: Optional[bool] = None
    can_export_leads: Optional[bool] = None
    can_send_messages: Optional[bool] = None
    price_cents: Optional[int] = None
    currency: Optional[str] = None
    is_active: Optional[bool] = None


@strawberry.input
class SponsorCreateInput:
    tier_id: Optional[str] = None
    company_name: str
    company_description: Optional[str] = None
    company_website: Optional[str] = None
    company_logo_url: Optional[str] = None
    contact_name: Optional[str] = None
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None
    booth_number: Optional[str] = None
    booth_description: Optional[str] = None
    custom_booth_url: Optional[str] = None
    social_links: Optional[str] = None  # JSON string
    marketing_assets: Optional[str] = None  # JSON string
    lead_capture_enabled: bool = True
    lead_notification_email: Optional[str] = None
    custom_fields: Optional[str] = None  # JSON string


@strawberry.input
class SponsorUpdateInput:
    tier_id: Optional[str] = None
    company_name: Optional[str] = None
    company_description: Optional[str] = None
    company_website: Optional[str] = None
    company_logo_url: Optional[str] = None
    contact_name: Optional[str] = None
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None
    booth_number: Optional[str] = None
    booth_description: Optional[str] = None
    custom_booth_url: Optional[str] = None
    social_links: Optional[str] = None  # JSON string
    marketing_assets: Optional[str] = None  # JSON string
    lead_capture_enabled: Optional[bool] = None
    lead_notification_email: Optional[str] = None
    custom_fields: Optional[str] = None  # JSON string
    is_active: Optional[bool] = None
    is_featured: Optional[bool] = None


@strawberry.input
class SponsorInvitationCreateInput:
    email: str
    role: str = "representative"
    can_view_leads: bool = True
    can_export_leads: bool = False
    can_message_attendees: bool = False
    can_manage_booth: bool = False
    can_invite_others: bool = False
    personal_message: Optional[str] = None


@strawberry.input
class SponsorLeadUpdateInput:
    follow_up_status: Optional[str] = None
    follow_up_notes: Optional[str] = None
    tags: Optional[List[str]] = None
    is_starred: Optional[bool] = None
    contact_notes: Optional[str] = None


# ============================================
# Response Types
# ============================================

@strawberry.type
class SponsorInvitationAcceptResponse:
    success: bool
    message: str
    sponsor_user: Optional[SponsorUserType]


@strawberry.type
class SponsorsListResponse:
    sponsors: List[SponsorType]
    total_count: int
