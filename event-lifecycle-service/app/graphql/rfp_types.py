# app/graphql/rfp_types.py
"""Strawberry GraphQL types for the RFP system."""
import strawberry
from typing import Optional, List
from datetime import datetime, date
from enum import Enum
from strawberry.scalars import JSON


# --- Enums ---

@strawberry.enum
class RFPEventTypeEnum(Enum):
    CONFERENCE = "conference"
    WEDDING = "wedding"
    CORPORATE_RETREAT = "corporate_retreat"
    WORKSHOP = "workshop"
    EXHIBITION = "exhibition"
    SOCIAL_EVENT = "social_event"
    OTHER = "other"


@strawberry.enum
class CateringNeedEnum(Enum):
    NONE = "none"
    IN_HOUSE_PREFERRED = "in_house_preferred"
    EXTERNAL_ALLOWED = "external_allowed"
    NO_PREFERENCE = "no_preference"


@strawberry.enum
class RFPStatusEnum(Enum):
    DRAFT = "draft"
    SENT = "sent"
    COLLECTING_RESPONSES = "collecting_responses"
    REVIEW = "review"
    AWARDED = "awarded"
    CLOSED = "closed"
    EXPIRED = "expired"


@strawberry.enum
class RFPVenueStatusEnum(Enum):
    RECEIVED = "received"
    VIEWED = "viewed"
    RESPONDED = "responded"
    SHORTLISTED = "shortlisted"
    AWARDED = "awarded"
    DECLINED = "declined"
    NO_RESPONSE = "no_response"


@strawberry.enum
class AvailabilityEnum(Enum):
    CONFIRMED = "confirmed"
    TENTATIVE = "tentative"
    UNAVAILABLE = "unavailable"


@strawberry.enum
class CapacityFitEnum(Enum):
    GOOD_FIT = "good_fit"
    TIGHT_FIT = "tight_fit"
    OVERSIZED = "oversized"
    POOR_FIT = "poor_fit"


# --- Output Types ---

@strawberry.type
class RFPAmenityType:
    id: str
    name: str
    category: str


@strawberry.type
class ExtraCostAmenityType:
    amenityId: str
    name: str
    price: float


@strawberry.type
class VenueResponseType:
    id: str
    availability: str
    proposedSpaceName: str
    proposedSpaceCapacity: Optional[int] = None
    currency: str
    spaceRentalPrice: Optional[float] = None
    cateringPricePerHead: Optional[float] = None
    avEquipmentFees: Optional[float] = None
    setupCleanupFees: Optional[float] = None
    otherFees: Optional[float] = None
    otherFeesDescription: Optional[str] = None
    totalEstimatedCost: float
    includedAmenityIds: List[str] = strawberry.field(default_factory=list)
    extraCostAmenities: List[ExtraCostAmenityType] = strawberry.field(default_factory=list)
    cancellationPolicy: Optional[str] = None
    depositAmount: Optional[float] = None
    paymentSchedule: Optional[str] = None
    alternativeDates: Optional[List[str]] = None
    quoteValidUntil: Optional[str] = None  # date as string
    notes: Optional[str] = None
    createdAt: Optional[datetime] = None


@strawberry.type
class RFPVenueType:
    id: str
    rfpId: str
    venueId: str
    venueName: str
    venueSlug: Optional[str] = None
    venueCity: Optional[str] = None
    venueCountry: Optional[str] = None
    venueVerified: bool = False
    venueCoverPhotoUrl: Optional[str] = None
    status: str
    capacityFit: Optional[str] = None
    amenityMatchPct: Optional[float] = None
    notifiedAt: Optional[datetime] = None
    viewedAt: Optional[datetime] = None
    respondedAt: Optional[datetime] = None
    hasResponse: bool = False
    response: Optional[VenueResponseType] = None


@strawberry.type
class RFPType:
    id: str
    organizationId: str
    title: str
    eventType: str
    attendanceMin: int
    attendanceMax: int
    preferredDatesStart: Optional[str] = None  # date as string
    preferredDatesEnd: Optional[str] = None
    datesFlexible: bool = False
    duration: str
    spaceRequirements: List[str] = strawberry.field(default_factory=list)
    requiredAmenities: List[RFPAmenityType] = strawberry.field(default_factory=list)
    cateringNeeds: str
    budgetMin: Optional[float] = None
    budgetMax: Optional[float] = None
    budgetCurrency: Optional[str] = None
    preferredCurrency: str = "USD"
    additionalNotes: Optional[str] = None
    responseDeadline: datetime
    linkedEventId: Optional[str] = None
    status: str
    sentAt: Optional[datetime] = None
    createdAt: Optional[datetime] = None
    updatedAt: Optional[datetime] = None
    venues: List[RFPVenueType] = strawberry.field(default_factory=list)
    venueCount: int = 0
    responseCount: int = 0


@strawberry.type
class RFPListResultType:
    rfps: List[RFPType]
    totalCount: int
    page: int
    pageSize: int
    totalPages: int


# --- Comparison Dashboard Types ---

@strawberry.type
class ExchangeRateType:
    base: str
    rates: JSON
    fetchedAt: str  # ISO datetime string


@strawberry.type
class ComparisonVenueResponseType:
    id: str
    availability: str
    proposedSpaceName: str
    proposedSpaceCapacity: Optional[int] = None
    currency: str
    spaceRentalPrice: Optional[float] = None
    cateringPricePerHead: Optional[float] = None
    avEquipmentFees: Optional[float] = None
    setupCleanupFees: Optional[float] = None
    otherFees: Optional[float] = None
    totalEstimatedCost: float
    totalInPreferredCurrency: float
    includedAmenityIds: List[str] = strawberry.field(default_factory=list)
    extraCostAmenities: List[ExtraCostAmenityType] = strawberry.field(default_factory=list)
    depositAmount: Optional[float] = None
    quoteValidUntil: Optional[str] = None
    cancellationPolicy: Optional[str] = None
    createdAt: Optional[datetime] = None


@strawberry.type
class ComparisonVenueType:
    rfvId: str
    venueId: str
    venueName: str
    venueVerified: bool = False
    venueSlug: Optional[str] = None
    status: str
    response: ComparisonVenueResponseType
    totalInPreferredCurrency: float = 0.0
    amenityMatchPct: float = 0.0
    responseTimeHours: float = 0.0
    badges: List[str] = strawberry.field(default_factory=list)


@strawberry.type
class ComparisonBadgesType:
    bestValue: Optional[str] = None
    bestMatch: Optional[str] = None


@strawberry.type
class ComparisonDashboardType:
    rfpId: str
    preferredCurrency: str
    exchangeRates: Optional[ExchangeRateType] = None
    requiredAmenityCount: int
    venues: List[ComparisonVenueType] = strawberry.field(default_factory=list)
    badges: ComparisonBadgesType


# --- Venue Owner Types ---

@strawberry.type
class VenueRFPInboxItemType:
    rfvId: str
    rfpId: str
    title: str
    eventType: str
    organizerName: str
    attendanceRange: str
    preferredDates: str
    status: str
    responseDeadline: datetime
    receivedAt: Optional[datetime] = None


@strawberry.type
class VenueRFPInboxResultType:
    rfps: List[VenueRFPInboxItemType]
    totalCount: int
    page: int
    pageSize: int
    totalPages: int


@strawberry.type
class VenueRFPSpaceType:
    id: str
    name: str
    capacity: Optional[int] = None
    layoutOptions: List[str] = strawberry.field(default_factory=list)


@strawberry.type
class VenueRFPDetailType:
    rfvId: str
    rfpId: str
    title: str
    eventType: str
    attendanceMin: int
    attendanceMax: int
    preferredDatesStart: Optional[str] = None
    preferredDatesEnd: Optional[str] = None
    datesFlexible: bool = False
    duration: str
    spaceRequirements: List[str] = strawberry.field(default_factory=list)
    requiredAmenities: List[RFPAmenityType] = strawberry.field(default_factory=list)
    cateringNeeds: str
    additionalNotes: Optional[str] = None
    responseDeadline: datetime
    status: str
    venueSpaces: List[VenueRFPSpaceType] = strawberry.field(default_factory=list)
    existingResponse: Optional[VenueResponseType] = None


# --- Pre-send Summary Types ---

@strawberry.type
class PreSendVenueFitType:
    venueId: str
    venueName: str
    venueCapacity: Optional[int] = None
    capacityFit: str
    capacityFitColor: str
    amenityMatchPct: float
    amenityMatchColor: str
    matchedAmenities: List[str] = strawberry.field(default_factory=list)
    missingAmenities: List[str] = strawberry.field(default_factory=list)
    priceIndicator: str
    priceIndicatorDetail: Optional[str] = None


@strawberry.type
class PreSendSummaryType:
    rfpId: str
    venueCount: int
    venues: List[PreSendVenueFitType] = strawberry.field(default_factory=list)


# --- Input Types ---

@strawberry.input
class RFPCreateInput:
    title: str
    eventType: str
    attendanceMin: int
    attendanceMax: int
    preferredDatesStart: Optional[str] = None  # date string
    preferredDatesEnd: Optional[str] = None
    datesFlexible: Optional[bool] = False
    duration: str
    spaceRequirements: Optional[List[str]] = None
    requiredAmenityIds: Optional[List[str]] = None
    cateringNeeds: str
    budgetMin: Optional[float] = None
    budgetMax: Optional[float] = None
    budgetCurrency: Optional[str] = None
    preferredCurrency: Optional[str] = "USD"
    additionalNotes: Optional[str] = None
    responseDeadline: datetime
    linkedEventId: Optional[str] = None


@strawberry.input
class RFPUpdateInput:
    title: Optional[str] = None
    eventType: Optional[str] = None
    attendanceMin: Optional[int] = None
    attendanceMax: Optional[int] = None
    preferredDatesStart: Optional[str] = None
    preferredDatesEnd: Optional[str] = None
    datesFlexible: Optional[bool] = None
    duration: Optional[str] = None
    spaceRequirements: Optional[List[str]] = None
    requiredAmenityIds: Optional[List[str]] = None
    cateringNeeds: Optional[str] = None
    budgetMin: Optional[float] = None
    budgetMax: Optional[float] = None
    budgetCurrency: Optional[str] = None
    preferredCurrency: Optional[str] = None
    additionalNotes: Optional[str] = None
    responseDeadline: Optional[datetime] = None
    linkedEventId: Optional[str] = None


@strawberry.input
class ExtraCostAmenityInput:
    amenityId: str
    name: str
    price: float


@strawberry.input
class VenueResponseInput:
    availability: str
    proposedSpaceId: Optional[str] = None
    currency: str
    spaceRentalPrice: Optional[float] = None
    cateringPricePerHead: Optional[float] = None
    avEquipmentFees: Optional[float] = None
    setupCleanupFees: Optional[float] = None
    otherFees: Optional[float] = None
    otherFeesDescription: Optional[str] = None
    includedAmenityIds: Optional[List[str]] = None
    extraCostAmenities: Optional[List[ExtraCostAmenityInput]] = None
    cancellationPolicy: Optional[str] = None
    depositAmount: Optional[float] = None
    paymentSchedule: Optional[str] = None
    alternativeDates: Optional[List[str]] = None
    quoteValidUntil: Optional[str] = None  # date string
    notes: Optional[str] = None
