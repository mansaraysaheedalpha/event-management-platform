# app/schemas/amenity.py
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime


class AmenityBase(BaseModel):
    name: str
    icon: Optional[str] = None
    sort_order: int = 0


class AmenityCategoryCreate(BaseModel):
    name: str
    icon: Optional[str] = None
    sort_order: int = 0


class AmenityCreate(BaseModel):
    category_id: str
    name: str
    description: Optional[str] = None
    icon: Optional[str] = None
    metadata_schema: Optional[dict] = None
    sort_order: int = 0


class AmenityUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    icon: Optional[str] = None
    metadata_schema: Optional[dict] = None
    sort_order: Optional[int] = None


class AmenityResponse(BaseModel):
    id: str
    category_id: str
    name: str
    icon: Optional[str] = None
    metadata_schema: Optional[dict] = None
    sort_order: int = 0

    model_config = {"from_attributes": True}


class AmenityCategoryResponse(BaseModel):
    id: str
    name: str
    icon: Optional[str] = None
    sort_order: int = 0
    amenities: List[AmenityResponse] = []

    model_config = {"from_attributes": True}


# --- Venue amenity set ---

class VenueAmenityItem(BaseModel):
    amenity_id: str
    metadata: Optional[dict] = None


class VenueAmenitySet(BaseModel):
    amenities: List[VenueAmenityItem]


class VenueAmenityResolved(BaseModel):
    amenity_id: str
    name: str
    category_name: str
    category_icon: Optional[str] = None
    metadata: Optional[dict] = None
