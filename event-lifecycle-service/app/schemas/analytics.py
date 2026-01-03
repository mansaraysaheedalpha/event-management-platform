# app/schemas/analytics.py
from typing import List, Optional, Dict, Any
from datetime import date, datetime
from pydantic import BaseModel, Field
from uuid import UUID


# ==================== Event Tracking DTOs ====================

class EventTrackingDTO(BaseModel):
    """Single event tracking data"""
    event_type: str = Field(
        ...,
        description="Type of event (OFFER_VIEW, AD_IMPRESSION, etc.)"
    )
    entity_type: str = Field(
        ...,
        description="Entity type (OFFER, AD, WAITLIST)"
    )
    entity_id: str = Field(..., description="ID of the offer, ad, or waitlist entry")
    revenue_cents: Optional[int] = Field(0, description="Revenue in cents (0 for non-purchase events)")
    context: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Additional context data")


class BatchTrackingDTO(BaseModel):
    """Batch of events to track"""
    events: List[EventTrackingDTO] = Field(..., min_items=1, max_items=100)


class TrackingResponse(BaseModel):
    """Response for event tracking"""
    status: str
    queued: int


# ==================== Analytics Response DTOs ====================

class RevenueBreakdown(BaseModel):
    """Revenue breakdown by source"""
    total_cents: int
    from_offers: int
    from_ads: int = 0  # Future: if ads have direct revenue
    by_day: List[Dict[str, Any]]


class OfferAnalytics(BaseModel):
    """Offer analytics summary"""
    total_views: int
    total_clicks: int
    total_add_to_cart: int
    total_purchases: int
    conversion_rate: float  # Overall view to purchase %
    view_to_click_rate: float
    click_to_cart_rate: float
    cart_to_purchase_rate: float
    top_performers: List[Dict[str, Any]]


class AdAnalyticsSummary(BaseModel):
    """Ad analytics summary"""
    total_impressions: int
    viewable_impressions: int
    total_clicks: int
    average_ctr: float
    by_placement: Dict[str, Dict[str, int]]


class WaitlistAnalytics(BaseModel):
    """Waitlist analytics summary"""
    total_joins: int
    offers_sent: int
    offers_accepted: int
    offers_declined: int
    offers_expired: int
    acceptance_rate: float


class MonetizationAnalyticsResponse(BaseModel):
    """
    Comprehensive monetization analytics for an event.
    Aggregates data from offers, ads, and waitlist.
    """
    event_id: str
    date_range: Dict[str, Optional[str]]  # {from: "2025-01-01", to: "2025-01-31"}

    revenue: RevenueBreakdown
    offers: OfferAnalytics
    ads: AdAnalyticsSummary
    waitlist: WaitlistAnalytics

    # Summary metrics
    total_interactions: int  # All tracked events
    unique_users: int  # Unique users across all features


# ==================== Conversion Funnel DTOs ====================

class ConversionFunnel(BaseModel):
    """Conversion funnel for a specific offer"""
    offer_id: str
    offer_name: Optional[str] = None
    views: int
    clicks: int
    add_to_cart: int
    purchases: int
    revenue_cents: int
    view_to_click_rate: float
    click_to_cart_rate: float
    cart_to_purchase_rate: float
    overall_conversion_rate: float


class ConversionFunnelsResponse(BaseModel):
    """List of conversion funnels"""
    event_id: str
    funnels: List[ConversionFunnel]
    summary: Dict[str, Any]  # Aggregate metrics


# ==================== Export DTOs ====================

class ExportFormat(str):
    """Supported export formats"""
    CSV = "csv"
    EXCEL = "excel"
    PDF = "pdf"


class ExportRequest(BaseModel):
    """Export report request"""
    format: str = Field("csv", description="Export format (csv, excel, pdf)")
    date_from: Optional[date] = None
    date_to: Optional[date] = None
    include_offers: bool = True
    include_ads: bool = True
    include_waitlist: bool = True
