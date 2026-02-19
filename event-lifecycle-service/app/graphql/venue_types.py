# app/graphql/venue_types.py
import strawberry
import typing
from typing import Optional, List
from datetime import datetime
from enum import Enum
from strawberry.types import Info
from strawberry.scalars import JSON


# --- Enums ---

@strawberry.enum
class VenueStatusEnum(Enum):
    DRAFT = "draft"
    PENDING_REVIEW = "pending_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    SUSPENDED = "suspended"


@strawberry.enum
class LayoutOptionEnum(Enum):
    THEATER = "theater"
    CLASSROOM = "classroom"
    BANQUET = "banquet"
    U_SHAPE = "u_shape"
    BOARDROOM = "boardroom"
    COCKTAIL = "cocktail"


@strawberry.enum
class RateTypeEnum(Enum):
    HOURLY = "hourly"
    HALF_DAY = "half_day"
    FULL_DAY = "full_day"


@strawberry.enum
class PhotoCategoryEnum(Enum):
    EXTERIOR = "exterior"
    INTERIOR = "interior"
    ROOMS = "rooms"
    AMENITIES = "amenities"
    CATERING = "catering"
    GENERAL = "general"


# --- Output Types ---

@strawberry.type
class VenueSpacePricingType:
    id: str
    spaceId: str
    rateType: str
    amount: float
    currency: str


@strawberry.type
class VenuePhotoType:
    id: str
    venueId: str
    spaceId: Optional[str] = None
    url: str
    category: Optional[str] = None
    caption: Optional[str] = None
    sortOrder: int = 0
    isCover: bool = False
    createdAt: Optional[datetime] = None


@strawberry.type
class VenueSpaceType:
    id: str
    venueId: str
    name: str
    description: Optional[str] = None
    capacity: Optional[int] = None
    floorLevel: Optional[str] = None
    layoutOptions: List[str] = strawberry.field(default_factory=list)
    sortOrder: int = 0
    pricing: List[VenueSpacePricingType] = strawberry.field(default_factory=list)
    photos: List[VenuePhotoType] = strawberry.field(default_factory=list)


@strawberry.type
class VenueAmenityType:
    amenityId: str
    name: str
    categoryName: str
    categoryIcon: Optional[str] = None
    metadata: Optional[JSON] = None


@strawberry.type
class VenueVerificationDocType:
    id: str
    documentType: str
    filename: str
    url: str
    status: str
    adminNotes: Optional[str] = None
    createdAt: Optional[datetime] = None


@strawberry.type
class VenueListedByType:
    name: str
    email: Optional[str] = None
    memberSince: Optional[datetime] = None


@strawberry.type
class VenuePriceType:
    amount: float
    currency: str
    rateType: str


@strawberry.type
class VenueFullType:
    """Extended venue type with all sourcing fields and nested resolvers."""
    id: str
    slug: Optional[str] = None
    organizationId: str
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
    totalCapacity: Optional[int] = None
    coverPhotoUrl: Optional[str] = None
    isPublic: bool = False
    status: str = "draft"
    rejectionReason: Optional[str] = None
    verified: bool = False
    domainMatch: bool = False
    submittedAt: Optional[datetime] = None
    approvedAt: Optional[datetime] = None
    isArchived: bool = False
    createdAt: Optional[datetime] = None
    updatedAt: Optional[datetime] = None

    # Availability status (Tier 1 - Waitlist System)
    availabilityStatus: str = "not_set"
    availabilityLastInferredAt: Optional[datetime] = None
    availabilityInferredStatus: Optional[str] = None
    availabilityManualOverrideAt: Optional[datetime] = None

    # Nested data
    spaces: List[VenueSpaceType] = strawberry.field(default_factory=list)
    photos: List[VenuePhotoType] = strawberry.field(default_factory=list)
    amenities: List[VenueAmenityType] = strawberry.field(default_factory=list)
    verificationDocuments: List[VenueVerificationDocType] = strawberry.field(default_factory=list)
    spaceCount: int = 0
    minPrice: Optional[VenuePriceType] = None
    amenityHighlights: List[str] = strawberry.field(default_factory=list)
    listedBy: Optional[VenueListedByType] = None


@strawberry.type
class AmenityTypeGQL:
    id: str
    categoryId: str
    name: str
    icon: Optional[str] = None
    sortOrder: int = 0


@strawberry.type
class AmenityCategoryTypeGQL:
    id: str
    name: str
    icon: Optional[str] = None
    sortOrder: int = 0
    amenities: List[AmenityTypeGQL] = strawberry.field(default_factory=list)


@strawberry.type
class VenueDirectoryResultGQL:
    venues: List[VenueFullType]
    totalCount: int
    page: int
    pageSize: int
    totalPages: int


@strawberry.type
class CountryCountGQL:
    code: str
    name: str
    venueCount: int


@strawberry.type
class CityCountGQL:
    name: str
    country: str
    venueCount: int


@strawberry.type
class VenueOwnerStatsType:
    """Dashboard statistics for venue owners."""
    pendingRfps: int
    totalBookings: int
    waitlistRequests: int


# --- Input Types ---

@strawberry.input
class VenueCreateInputGQL:
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
    isPublic: Optional[bool] = True


@strawberry.input
class VenueUpdateInputGQL:
    name: Optional[str] = None
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
    isPublic: Optional[bool] = None


@strawberry.input(name="VenueSpaceCreateInput")
class VenueSpaceCreateInputGQL:
    venueId: str
    name: str
    description: Optional[str] = None
    capacity: Optional[int] = None
    floorLevel: Optional[str] = None
    layoutOptions: Optional[List[str]] = None
    sortOrder: Optional[int] = 0


@strawberry.input(name="VenueSpaceUpdateInput")
class VenueSpaceUpdateInputGQL:
    name: Optional[str] = None
    description: Optional[str] = None
    capacity: Optional[int] = None
    floorLevel: Optional[str] = None
    layoutOptions: Optional[List[str]] = None
    sortOrder: Optional[int] = None


@strawberry.input(name="SpacePricingInput")
class SpacePricingInputGQL:
    rateType: str
    amount: float
    currency: str


@strawberry.input
class VenueAmenityInputGQL:
    amenityId: str
    metadata: Optional[JSON] = None
