# app/schemas/venue_waitlist.py
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime, date
from enum import Enum


# --- Enums ---

class WaitlistStatus(str, Enum):
    WAITING = "waiting"
    OFFERED = "offered"
    CONVERTED = "converted"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


class CancellationReason(str, Enum):
    NO_LONGER_NEEDED = "no_longer_needed"
    FOUND_ALTERNATIVE = "found_alternative"
    DECLINED_OFFER = "declined_offer"
    NUDGE_DECLINED = "nudge_declined"
    OTHER = "other"


class AvailabilityStatus(str, Enum):
    ACCEPTING_EVENTS = "accepting_events"
    LIMITED_AVAILABILITY = "limited_availability"
    FULLY_BOOKED = "fully_booked"
    SEASONAL = "seasonal"
    NOT_SET = "not_set"


class SignalType(str, Enum):
    CONFIRMED = "confirmed"
    TENTATIVE = "tentative"
    UNAVAILABLE = "unavailable"
    NO_RESPONSE = "no_response"
    AWARDED = "awarded"
    LOST_TO_COMPETITOR = "lost_to_competitor"
    RFP_CANCELLED = "rfp_cancelled"
    MANUAL_AVAILABLE = "manual_available"
    MANUAL_UNAVAILABLE = "manual_unavailable"


# --- Request Schemas ---

class WaitlistJoinRequest(BaseModel):
    source_rfp_venue_id: str = Field(..., description="The RFP venue response that was unavailable")


class WaitlistCancelRequest(BaseModel):
    reason: CancellationReason
    notes: Optional[str] = Field(None, max_length=1000)


class WaitlistStillInterestedRequest(BaseModel):
    interested: bool


class VenueAvailabilitySetRequest(BaseModel):
    availability_status: AvailabilityStatus

    def model_post_init(self, __context):
        # Validate that status is not "not_set" (that's system-only)
        if self.availability_status == AvailabilityStatus.NOT_SET:
            raise ValueError("Cannot manually set availability to 'not_set'")


# --- Response Schemas ---

class WaitlistEntryResponse(BaseModel):
    id: str
    organization_id: str
    venue_id: str
    venue_name: str
    venue_slug: Optional[str] = None
    venue_city: Optional[str] = None
    venue_country: Optional[str] = None
    venue_cover_photo_url: Optional[str] = None
    venue_availability_status: str = "not_set"

    source_rfp_id: str
    source_rfp_title: str
    source_rfp_venue_id: str

    desired_dates_start: Optional[date] = None
    desired_dates_end: Optional[date] = None
    dates_flexible: bool
    attendance_min: int
    attendance_max: int
    event_type: str
    space_requirements: List[str] = []

    status: str
    queue_position: Optional[int] = None  # null for terminal states

    hold_offered_at: Optional[datetime] = None
    hold_expires_at: Optional[datetime] = None
    hold_remaining_seconds: Optional[int] = None  # computed server-side
    hold_reminder_sent: bool = False

    converted_rfp_id: Optional[str] = None

    cancellation_reason: Optional[str] = None
    cancellation_notes: Optional[str] = None

    expires_at: datetime
    still_interested_sent_at: Optional[datetime] = None
    still_interested_responded: bool = False

    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class WaitlistEntryListResponse(BaseModel):
    waitlist_entries: List[WaitlistEntryResponse]
    pagination: dict


class RFPBasicInfo(BaseModel):
    id: str
    title: str
    status: str
    venue_count: int
    message: str

    model_config = {"from_attributes": True}


class WaitlistConversionResponse(BaseModel):
    waitlist_entry: WaitlistEntryResponse
    new_rfp: RFPBasicInfo


class AvailabilitySignalSummary(BaseModel):
    period_days: int
    total_responses: int
    confirmed_count: int
    tentative_count: int
    unavailable_count: int
    unavailable_ratio: float


class VenueAvailabilityResponse(BaseModel):
    venue_id: str
    availability_status: str
    is_manual_override: bool
    last_inferred_at: Optional[datetime] = None
    inferred_status: Optional[str] = None
    manual_override_at: Optional[datetime] = None
    signal_summary: Optional[AvailabilitySignalSummary] = None

    model_config = {"from_attributes": True}


class AvailabilityBadgeResponse(BaseModel):
    venue_id: str
    availability_status: str
    badge_color: str
    badge_label: str

    model_config = {"from_attributes": True}


class CircuitBreakerResolveResponse(BaseModel):
    venue_id: str
    circuit_breaker_resolved: bool
    cascade_resumed: bool
    next_entry_offered: Optional[str] = None
