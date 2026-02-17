# app/schemas/rfp_venue.py
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime


class AddVenuesRequest(BaseModel):
    venue_ids: List[str]


class RFPVenueAddedItem(BaseModel):
    id: str
    venue_id: str
    venue_name: str
    capacity_fit: Optional[str] = None
    amenity_match_pct: Optional[float] = None
    status: str

    model_config = {"from_attributes": True}


class AddVenuesResponse(BaseModel):
    added: List[RFPVenueAddedItem]
    skipped: List[str] = []


class RFPVenueResponse(BaseModel):
    id: str
    rfp_id: str
    venue_id: str
    status: str
    notified_at: Optional[datetime] = None
    viewed_at: Optional[datetime] = None
    responded_at: Optional[datetime] = None
    capacity_fit: Optional[str] = None
    amenity_match_pct: Optional[float] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class DeclineVenueRequest(BaseModel):
    reason: Optional[str] = None


# --- Pre-send summary ---

class PreSendVenueFit(BaseModel):
    venue_id: str
    venue_name: str
    venue_capacity: Optional[int] = None
    capacity_fit: str
    capacity_fit_color: str
    amenity_match_pct: float
    amenity_match_color: str
    matched_amenities: List[str] = []
    missing_amenities: List[str] = []
    price_indicator: str
    price_indicator_detail: Optional[str] = None


class PreSendSummary(BaseModel):
    rfp_id: str
    venue_count: int
    venues: List[PreSendVenueFit]
