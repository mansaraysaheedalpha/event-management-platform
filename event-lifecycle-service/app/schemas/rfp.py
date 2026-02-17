# app/schemas/rfp.py
from pydantic import BaseModel, Field, model_validator
from typing import Optional, List
from datetime import datetime, date
from decimal import Decimal
from enum import Enum


# --- Enums ---

class EventType(str, Enum):
    CONFERENCE = "conference"
    WEDDING = "wedding"
    CORPORATE_RETREAT = "corporate_retreat"
    WORKSHOP = "workshop"
    EXHIBITION = "exhibition"
    SOCIAL_EVENT = "social_event"
    OTHER = "other"


class CateringNeed(str, Enum):
    NONE = "none"
    IN_HOUSE_PREFERRED = "in_house_preferred"
    EXTERNAL_ALLOWED = "external_allowed"
    NO_PREFERENCE = "no_preference"


class RFPStatus(str, Enum):
    DRAFT = "draft"
    SENT = "sent"
    COLLECTING_RESPONSES = "collecting_responses"
    REVIEW = "review"
    AWARDED = "awarded"
    CLOSED = "closed"
    EXPIRED = "expired"


VALID_LAYOUT_TYPES = {
    "theater", "classroom", "banquet", "u_shape", "boardroom", "cocktail",
    "u-shape",  # accept hyphenated too
}


# --- Create / Update ---

class RFPCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=500)
    event_type: EventType
    attendance_min: int = Field(..., ge=1)
    attendance_max: int = Field(..., ge=1)
    preferred_dates_start: Optional[date] = None
    preferred_dates_end: Optional[date] = None
    dates_flexible: bool = False
    duration: str = Field(..., min_length=1, max_length=200)
    space_requirements: List[str] = []
    required_amenity_ids: List[str] = []
    catering_needs: CateringNeed
    budget_min: Optional[Decimal] = Field(None, ge=0)
    budget_max: Optional[Decimal] = Field(None, ge=0)
    budget_currency: Optional[str] = Field(None, max_length=3)
    preferred_currency: str = Field("USD", max_length=3)
    additional_notes: Optional[str] = None
    response_deadline: datetime
    linked_event_id: Optional[str] = None

    @model_validator(mode="after")
    def validate_ranges(self):
        if self.attendance_min > self.attendance_max:
            raise ValueError("attendance_min must be <= attendance_max")
        if self.budget_min is not None and self.budget_max is not None:
            if self.budget_min > self.budget_max:
                raise ValueError("budget_min must be <= budget_max")
        if self.preferred_dates_start and self.preferred_dates_end:
            if self.preferred_dates_start > self.preferred_dates_end:
                raise ValueError("preferred_dates_start must be <= preferred_dates_end")
        return self


class RFPUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=500)
    event_type: Optional[EventType] = None
    attendance_min: Optional[int] = Field(None, ge=1)
    attendance_max: Optional[int] = Field(None, ge=1)
    preferred_dates_start: Optional[date] = None
    preferred_dates_end: Optional[date] = None
    dates_flexible: Optional[bool] = None
    duration: Optional[str] = Field(None, min_length=1, max_length=200)
    space_requirements: Optional[List[str]] = None
    required_amenity_ids: Optional[List[str]] = None
    catering_needs: Optional[CateringNeed] = None
    budget_min: Optional[Decimal] = Field(None, ge=0)
    budget_max: Optional[Decimal] = Field(None, ge=0)
    budget_currency: Optional[str] = Field(None, max_length=3)
    preferred_currency: Optional[str] = Field(None, max_length=3)
    additional_notes: Optional[str] = None
    response_deadline: Optional[datetime] = None
    linked_event_id: Optional[str] = None


# --- Response shapes ---

class RFPAmenityInfo(BaseModel):
    id: str
    name: str
    category: str

    model_config = {"from_attributes": True}


class RFPVenueListItem(BaseModel):
    id: str  # rfv_ ID
    venue_id: str
    venue_name: str
    venue_slug: Optional[str] = None
    venue_city: Optional[str] = None
    venue_country: Optional[str] = None
    venue_verified: bool = False
    venue_cover_photo_url: Optional[str] = None
    status: str
    capacity_fit: Optional[str] = None
    amenity_match_pct: Optional[float] = None
    notified_at: Optional[datetime] = None
    viewed_at: Optional[datetime] = None
    responded_at: Optional[datetime] = None
    has_response: bool = False

    model_config = {"from_attributes": True}


class RFPResponse(BaseModel):
    id: str
    organization_id: str
    title: str
    event_type: str
    attendance_min: int
    attendance_max: int
    preferred_dates_start: Optional[date] = None
    preferred_dates_end: Optional[date] = None
    dates_flexible: bool
    duration: str
    space_requirements: List[str] = []
    required_amenities: List[RFPAmenityInfo] = []
    catering_needs: str
    budget_min: Optional[float] = None
    budget_max: Optional[float] = None
    budget_currency: Optional[str] = None
    preferred_currency: str
    additional_notes: Optional[str] = None
    response_deadline: datetime
    linked_event_id: Optional[str] = None
    status: str
    sent_at: Optional[datetime] = None
    venues: List[RFPVenueListItem] = []
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class RFPListItem(BaseModel):
    id: str
    title: str
    event_type: str
    status: str
    attendance_max: int
    preferred_dates_start: Optional[date] = None
    response_deadline: datetime
    venue_count: int = 0
    response_count: int = 0
    sent_at: Optional[datetime] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class PaginationInfo(BaseModel):
    page: int
    page_size: int
    total_count: int
    total_pages: int


class RFPListResult(BaseModel):
    rfps: List[RFPListItem]
    pagination: PaginationInfo


# --- Action request/response shapes ---

class ExtendDeadlineRequest(BaseModel):
    new_deadline: datetime


class CloseRFPRequest(BaseModel):
    reason: Optional[str] = None


class SendRFPResponse(BaseModel):
    id: str
    status: str
    sent_at: datetime
    venues_notified: int
