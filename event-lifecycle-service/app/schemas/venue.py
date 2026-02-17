#app/schemas/venue.py
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from enum import Enum


# --- Enums ---

class VenueStatus(str, Enum):
    DRAFT = "draft"
    PENDING_REVIEW = "pending_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    SUSPENDED = "suspended"


# --- Base schemas (backwards compatible) ---

class VenueBase(BaseModel):
    name: str = Field(..., json_schema_extra={"example": "Grand Convention Center"})
    address: Optional[str] = Field(None, json_schema_extra={"example": "123 Innovation Drive, Tech City"})


class VenueCreate(VenueBase):
    description: Optional[str] = None
    city: Optional[str] = None
    country: Optional[str] = Field(None, max_length=2)
    latitude: Optional[float] = Field(None, ge=-90, le=90)
    longitude: Optional[float] = Field(None, ge=-180, le=180)
    website: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    whatsapp: Optional[str] = None
    is_public: Optional[bool] = False


class VenueUpdate(BaseModel):
    name: Optional[str] = None
    address: Optional[str] = None
    description: Optional[str] = None
    city: Optional[str] = None
    country: Optional[str] = Field(None, max_length=2)
    latitude: Optional[float] = Field(None, ge=-90, le=90)
    longitude: Optional[float] = Field(None, ge=-180, le=180)
    website: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    whatsapp: Optional[str] = None
    is_public: Optional[bool] = None


class Venue(VenueBase):
    id: str
    organization_id: str
    slug: Optional[str] = None
    description: Optional[str] = None
    city: Optional[str] = None
    country: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    website: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    whatsapp: Optional[str] = None
    cover_photo_id: Optional[str] = None
    total_capacity: Optional[int] = None
    is_public: bool = False
    status: str = "draft"
    rejection_reason: Optional[str] = None
    submitted_at: Optional[datetime] = None
    approved_at: Optional[datetime] = None
    verified: bool = False
    domain_match: bool = False
    is_archived: bool
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


# --- Directory-specific response schemas ---

class VenueMinPrice(BaseModel):
    amount: float
    currency: str
    rate_type: str


class VenueDirectoryItem(BaseModel):
    """Lightweight venue card for listing page."""
    id: str
    slug: str
    name: str
    city: Optional[str] = None
    country: Optional[str] = None
    address: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    total_capacity: Optional[int] = None
    verified: bool = False
    cover_photo_url: Optional[str] = None
    space_count: int = 0
    min_price: Optional[VenueMinPrice] = None
    amenity_highlights: List[str] = []
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class PaginationInfo(BaseModel):
    page: int
    page_size: int
    total_count: int
    total_pages: int


class VenueDirectoryResult(BaseModel):
    venues: List[VenueDirectoryItem]
    pagination: PaginationInfo


# --- Directory detail response schemas ---

class VenuePhotoResponse(BaseModel):
    id: str
    url: str
    category: Optional[str] = None
    caption: Optional[str] = None
    is_cover: bool = False
    sort_order: int = 0

    model_config = {"from_attributes": True}


class VenueSpacePricingResponse(BaseModel):
    rate_type: str
    amount: float
    currency: str

    model_config = {"from_attributes": True}


class VenueSpaceResponse(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    capacity: Optional[int] = None
    floor_level: Optional[str] = None
    layout_options: List[str] = []
    pricing: List[VenueSpacePricingResponse] = []
    photos: List[VenuePhotoResponse] = []

    model_config = {"from_attributes": True}


class VenueAmenityResponse(BaseModel):
    id: str
    name: str
    category: str
    category_icon: Optional[str] = None
    metadata: Optional[dict] = None

    model_config = {"from_attributes": True}


class VenueListedBy(BaseModel):
    name: str
    member_since: Optional[datetime] = None


class VenueDirectoryDetail(BaseModel):
    """Full venue profile for detail page."""
    id: str
    slug: str
    name: str
    description: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    country: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    website: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    whatsapp: Optional[str] = None
    total_capacity: Optional[int] = None
    verified: bool = False
    cover_photo_url: Optional[str] = None
    photos: List[VenuePhotoResponse] = []
    spaces: List[VenueSpaceResponse] = []
    amenities: List[VenueAmenityResponse] = []
    listed_by: Optional[VenueListedBy] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


# --- Country/City responses ---

class CountryCount(BaseModel):
    code: str
    name: str
    venue_count: int


class CityCount(BaseModel):
    name: str
    country: str
    venue_count: int


# --- Submit response ---

class VenueSubmitResponse(BaseModel):
    id: str
    status: str
    submitted_at: Optional[datetime] = None


# --- Admin responses ---

class VenueAdminApproveResponse(BaseModel):
    id: str
    status: str
    verified: bool
    approved_at: Optional[datetime] = None


class VenueAdminRejectResponse(BaseModel):
    id: str
    status: str
    rejection_reason: Optional[str] = None


class AdminRejectRequest(BaseModel):
    reason: str = Field(..., min_length=1)


class AdminSuspendRequest(BaseModel):
    reason: str = Field(..., min_length=1)


class AdminVenueSuspendResponse(BaseModel):
    id: str
    status: str


class AdminVerificationStatusUpdate(BaseModel):
    status: str = Field(..., pattern="^(accepted|rejected)$")
    admin_notes: Optional[str] = None


class AdminRequestDocumentsRequest(BaseModel):
    message: str = Field(..., min_length=1)
