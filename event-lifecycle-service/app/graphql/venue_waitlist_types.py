# app/graphql/venue_waitlist_types.py
"""Strawberry GraphQL types for the Venue Waitlist system."""
import strawberry
from typing import Optional, List
from datetime import datetime, date
from enum import Enum
from strawberry.scalars import JSON


# --- Enums (API Contract Section 3.1) ---


@strawberry.enum
class WaitlistStatusEnum(Enum):
    WAITING = "waiting"
    OFFERED = "offered"
    CONVERTED = "converted"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


@strawberry.enum
class CancellationReasonEnum(Enum):
    NO_LONGER_NEEDED = "no_longer_needed"
    FOUND_ALTERNATIVE = "found_alternative"
    DECLINED_OFFER = "declined_offer"
    NUDGE_DECLINED = "nudge_declined"
    OTHER = "other"


@strawberry.enum
class AvailabilityStatusEnum(Enum):
    ACCEPTING_EVENTS = "accepting_events"
    LIMITED_AVAILABILITY = "limited_availability"
    FULLY_BOOKED = "fully_booked"
    SEASONAL = "seasonal"
    NOT_SET = "not_set"


@strawberry.enum
class SignalTypeEnum(Enum):
    CONFIRMED = "confirmed"
    TENTATIVE = "tentative"
    UNAVAILABLE = "unavailable"
    NO_RESPONSE = "no_response"
    AWARDED = "awarded"
    LOST_TO_COMPETITOR = "lost_to_competitor"
    RFP_CANCELLED = "rfp_cancelled"
    MANUAL_AVAILABLE = "manual_available"
    MANUAL_UNAVAILABLE = "manual_unavailable"


# --- Output Types (API Contract Section 3.2) ---


@strawberry.type
class VenueWaitlistEntryType:
    """Full waitlist entry with all fields."""
    id: str
    organizationId: str
    venueId: str
    venueName: str
    venueSlug: Optional[str] = None
    venueCoverPhotoUrl: Optional[str] = None
    venueCity: Optional[str] = None
    venueCountry: Optional[str] = None
    venueAvailabilityStatus: str = "not_set"

    sourceRfpId: str
    sourceRfpTitle: str
    sourceRfpVenueId: str

    desiredDatesStart: Optional[str] = None  # date as string
    desiredDatesEnd: Optional[str] = None
    datesFlexible: bool = False
    attendanceMin: int
    attendanceMax: int
    eventType: str
    spaceRequirements: List[str] = strawberry.field(default_factory=list)

    status: str
    queuePosition: Optional[int] = None  # null for terminal states

    holdOfferedAt: Optional[datetime] = None
    holdExpiresAt: Optional[datetime] = None
    holdRemainingSeconds: Optional[int] = None  # computed server-side
    holdReminderSent: bool = False

    convertedRfpId: Optional[str] = None

    cancellationReason: Optional[str] = None
    cancellationNotes: Optional[str] = None

    expiresAt: datetime
    stillInterestedSentAt: Optional[datetime] = None
    stillInterestedResponded: bool = False

    createdAt: datetime
    updatedAt: datetime


@strawberry.type
class WaitlistEntryListResult:
    """Paginated list of waitlist entries."""
    entries: List[VenueWaitlistEntryType]
    totalCount: int
    page: int
    pageSize: int
    totalPages: int


@strawberry.type
class RFPBasicInfoType:
    """Basic RFP info for conversion response."""
    id: str
    title: str
    status: str
    venueCount: int
    message: str


@strawberry.type
class WaitlistConversionResult:
    """Result of converting a waitlist hold to an RFP."""
    waitlistEntry: VenueWaitlistEntryType
    newRfp: RFPBasicInfoType


@strawberry.type
class AvailabilitySignalSummary:
    """Signal counts for inference display."""
    periodDays: int
    totalResponses: int
    confirmedCount: int
    tentativeCount: int
    unavailableCount: int
    unavailableRatio: float


@strawberry.type
class VenueAvailabilityType:
    """Venue availability detail (owner view)."""
    venueId: str
    availabilityStatus: str
    isManualOverride: bool
    lastInferredAt: Optional[datetime] = None
    inferredStatus: Optional[str] = None
    manualOverrideAt: Optional[datetime] = None
    signalSummary: Optional[AvailabilitySignalSummary] = None


@strawberry.type
class AvailabilityBadge:
    """Public availability badge for directory listings."""
    venueId: str
    availabilityStatus: str
    badgeColor: str
    badgeLabel: str


# --- Input Types ---


@strawberry.input
class JoinVenueWaitlistInput:
    """Input for joining a venue waitlist."""
    sourceRfpVenueId: str


@strawberry.input
class CancelWaitlistEntryInput:
    """Input for cancelling a waitlist entry."""
    reason: CancellationReasonEnum
    notes: Optional[str] = None


@strawberry.input
class SetVenueAvailabilityInput:
    """Input for setting venue availability (manual override)."""
    status: AvailabilityStatusEnum


# --- Response Types for Mutations ---


@strawberry.type
class JoinWaitlistResponse:
    """Response from joining a venue waitlist."""
    success: bool
    waitlistEntry: Optional[VenueWaitlistEntryType] = None
    message: str


@strawberry.type
class ConvertHoldResponse:
    """Response from converting a hold to an RFP."""
    success: bool
    newRfpId: Optional[str] = None
    waitlistEntryId: str
    message: str


@strawberry.type
class CancelWaitlistResponse:
    """Response from cancelling a waitlist entry."""
    success: bool
    waitlistEntryId: str
    message: str


@strawberry.type
class RespondStillInterestedResponse:
    """Response from responding to still interested nudge."""
    success: bool
    waitlistEntryId: str
    stillInterested: bool
    message: str


@strawberry.type
class SetAvailabilityResponse:
    """Response from setting venue availability status."""
    success: bool
    venueId: str
    availabilityStatus: AvailabilityStatusEnum
    isManualOverride: bool
    manualOverrideAt: Optional[datetime] = None


@strawberry.type
class ClearOverrideResponse:
    """Response from clearing manual availability override."""
    success: bool
    venueId: str
    availabilityStatus: AvailabilityStatusEnum
    isManualOverride: bool
    revertedToInferred: bool


@strawberry.type
class ResolveCircuitBreakerResponse:
    """Response from manually resolving circuit breaker."""
    success: bool
    venueId: str
    circuitBreakerResolved: bool
    cascadeResumed: bool
    nextEntryOffered: Optional[str] = None
    message: str
