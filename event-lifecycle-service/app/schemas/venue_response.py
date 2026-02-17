# app/schemas/venue_response.py
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime, date
from decimal import Decimal
from enum import Enum


class Availability(str, Enum):
    CONFIRMED = "confirmed"
    TENTATIVE = "tentative"
    UNAVAILABLE = "unavailable"


class ExtraCostAmenity(BaseModel):
    amenity_id: str
    name: str
    price: float


class VenueResponseCreate(BaseModel):
    availability: Availability
    proposed_space_id: Optional[str] = None
    currency: str = Field(..., max_length=3)
    space_rental_price: Optional[Decimal] = Field(None, ge=0)
    catering_price_per_head: Optional[Decimal] = Field(None, ge=0)
    av_equipment_fees: Optional[Decimal] = Field(None, ge=0)
    setup_cleanup_fees: Optional[Decimal] = Field(None, ge=0)
    other_fees: Optional[Decimal] = Field(None, ge=0)
    other_fees_description: Optional[str] = None
    included_amenity_ids: List[str] = []
    extra_cost_amenities: List[ExtraCostAmenity] = []
    cancellation_policy: Optional[str] = None
    deposit_amount: Optional[Decimal] = Field(None, ge=0)
    payment_schedule: Optional[str] = None
    alternative_dates: Optional[List[str]] = None
    quote_valid_until: Optional[date] = None
    notes: Optional[str] = None


class VenueResponseResponse(BaseModel):
    id: str
    rfp_venue_id: str
    availability: str
    proposed_space_id: Optional[str] = None
    proposed_space_name: str
    proposed_space_capacity: Optional[int] = None
    currency: str
    space_rental_price: Optional[float] = None
    catering_price_per_head: Optional[float] = None
    av_equipment_fees: Optional[float] = None
    setup_cleanup_fees: Optional[float] = None
    other_fees: Optional[float] = None
    other_fees_description: Optional[str] = None
    total_estimated_cost: float
    included_amenity_ids: List[str] = []
    extra_cost_amenities: List[ExtraCostAmenity] = []
    cancellation_policy: Optional[str] = None
    deposit_amount: Optional[float] = None
    payment_schedule: Optional[str] = None
    alternative_dates: Optional[List[str]] = None
    quote_valid_until: Optional[date] = None
    notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# --- Comparison Dashboard ---

class ExchangeRateData(BaseModel):
    base: str
    rates: dict
    fetched_at: datetime
    source: str = "exchangerate-api.com"


class ComparisonVenueResponse(BaseModel):
    """Venue response data within the comparison dashboard."""
    id: str
    availability: str
    proposed_space_name: str
    proposed_space_capacity: Optional[int] = None
    currency: str
    space_rental_price: Optional[float] = None
    catering_price_per_head: Optional[float] = None
    av_equipment_fees: Optional[float] = None
    setup_cleanup_fees: Optional[float] = None
    other_fees: Optional[float] = None
    total_estimated_cost: float
    total_in_preferred_currency: float
    included_amenity_ids: List[str] = []
    extra_cost_amenities: List[ExtraCostAmenity] = []
    deposit_amount: Optional[float] = None
    quote_valid_until: Optional[date] = None
    cancellation_policy: Optional[str] = None
    created_at: datetime


class ComparisonVenue(BaseModel):
    rfv_id: str
    venue_id: str
    venue_name: str
    venue_verified: bool
    venue_slug: Optional[str] = None
    status: str
    response: ComparisonVenueResponse
    amenity_match_pct: float
    response_time_hours: float
    badges: List[str] = []


class ComparisonBadges(BaseModel):
    best_value: Optional[str] = None  # rfv_id
    best_match: Optional[str] = None  # rfv_id


class ComparisonDashboard(BaseModel):
    rfp_id: str
    preferred_currency: str
    exchange_rates: Optional[ExchangeRateData] = None
    required_amenity_count: int
    venues: List[ComparisonVenue] = []
    badges: ComparisonBadges


# --- Venue owner view schemas ---

class VenueRFPInboxItem(BaseModel):
    rfv_id: str
    rfp_id: str
    title: str
    event_type: str
    organizer_name: str
    attendance_range: str
    preferred_dates: str
    status: str
    response_deadline: datetime
    received_at: Optional[datetime] = None


class VenueRFPInboxResult(BaseModel):
    rfps: List[VenueRFPInboxItem]
    pagination: dict


class VenueSpaceForRFP(BaseModel):
    id: str
    name: str
    capacity: Optional[int] = None
    layout_options: List[str] = []

    model_config = {"from_attributes": True}


class VenueRFPDetail(BaseModel):
    rfv_id: str
    rfp_id: str
    title: str
    event_type: str
    attendance_min: int
    attendance_max: int
    preferred_dates_start: Optional[date] = None
    preferred_dates_end: Optional[date] = None
    dates_flexible: bool
    duration: str
    space_requirements: List[str] = []
    required_amenities: List[dict] = []
    catering_needs: str
    additional_notes: Optional[str] = None
    response_deadline: datetime
    status: str
    venue_spaces: List[VenueSpaceForRFP] = []
    existing_response: Optional[VenueResponseResponse] = None
