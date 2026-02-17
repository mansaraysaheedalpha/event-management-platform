# app/schemas/venue_space.py
from pydantic import BaseModel, Field
from typing import Optional, List, Literal
from datetime import datetime


class VenueSpaceCreate(BaseModel):
    name: str
    description: Optional[str] = None
    capacity: Optional[int] = None
    floor_level: Optional[str] = None
    layout_options: Optional[List[str]] = []
    sort_order: Optional[int] = 0


class VenueSpaceUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    capacity: Optional[int] = None
    floor_level: Optional[str] = None
    layout_options: Optional[List[str]] = None
    sort_order: Optional[int] = None


class VenueSpace(BaseModel):
    id: str
    venue_id: str
    name: str
    description: Optional[str] = None
    capacity: Optional[int] = None
    floor_level: Optional[str] = None
    layout_options: List[str] = []
    sort_order: int = 0
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


# --- Pricing schemas ---

class SpacePricingItem(BaseModel):
    rate_type: Literal["hourly", "half_day", "full_day"]
    amount: float = Field(..., gt=0)
    currency: str = Field(..., min_length=3, max_length=3)


class SpacePricingSet(BaseModel):
    pricing: List[SpacePricingItem]


class VenueSpacePricing(BaseModel):
    id: str
    space_id: str
    rate_type: str
    amount: float
    currency: str
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}
