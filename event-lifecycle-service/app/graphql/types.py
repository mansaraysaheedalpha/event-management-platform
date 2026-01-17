# app/graphql/types.py
import strawberry
import typing
from typing import Optional
import json
from datetime import datetime, timedelta
from enum import Enum
from ..models.event import Event as EventModel
from .. import crud
from strawberry.types import Info
from ..models.venue import Venue as VenueModel
from ..models.registration import Registration as RegistrationModel
from ..models.session import Session as SessionModel


# ==== VIRTUAL EVENT ENUMS (Phase 1) ====

@strawberry.enum
class EventTypeEnum(Enum):
    """Event type classification for virtual event support."""
    IN_PERSON = "IN_PERSON"
    VIRTUAL = "VIRTUAL"
    HYBRID = "HYBRID"


@strawberry.enum
class SessionTypeEnum(Enum):
    """Session type classification for virtual event support."""
    MAINSTAGE = "MAINSTAGE"
    BREAKOUT = "BREAKOUT"
    WORKSHOP = "WORKSHOP"
    NETWORKING = "NETWORKING"
    EXPO = "EXPO"


@strawberry.type
class VirtualSettingsType:
    """Virtual event configuration settings."""
    streamingProvider: Optional[str] = None
    streamingUrl: Optional[str] = None
    recordingEnabled: bool = True
    autoCaptions: bool = False
    timezoneDisplay: Optional[str] = None
    lobbyEnabled: bool = False
    lobbyVideoUrl: Optional[str] = None
    maxConcurrentViewers: Optional[int] = None
    geoRestrictions: Optional[typing.List[str]] = None


@strawberry.type
class EventsPayload:
    events: typing.List["EventType"]
    totalCount: int


@strawberry.type
class EventStatsType:
    totalEvents: int
    upcomingEvents: int
    upcomingRegistrations: int


@strawberry.federation.type(keys=["id"], extend=True)
class User:
    id: strawberry.ID = strawberry.federation.field(external=True)


@strawberry.type
class SpeakerType:
    id: str
    organization_id: str
    name: str
    bio: typing.Optional[str]
    expertise: typing.Optional[list[str]]
    is_archived: bool
    user_id: typing.Optional[str]  # Links speaker to a platform user account


@strawberry.type
class VenueType:
    id: str
    organization_id: str
    name: str
    address: Optional[str]
    is_archived: bool


@strawberry.type
class EventType:
    @strawberry.field
    def id(self, root) -> str:
        return root["id"] if isinstance(root, dict) else root.id

    @strawberry.field
    def organization_id(self, root) -> str:
        return (
            root["organization_id"] if isinstance(root, dict) else root.organization_id
        )

    @strawberry.field
    def owner_id(self, root) -> str:
        return root["owner_id"] if isinstance(root, dict) else root.owner_id

    @strawberry.field
    def name(self, root) -> str:
        return root["name"] if isinstance(root, dict) else root.name

    @strawberry.field
    def version(self, root) -> int:
        return root["version"] if isinstance(root, dict) else root.version

    @strawberry.field
    def description(self, root) -> typing.Optional[str]:
        return root.get("description") if isinstance(root, dict) else root.description

    @strawberry.field
    def status(self, root) -> str:
        return root["status"] if isinstance(root, dict) else root.status

    @strawberry.field
    def is_archived(self, root) -> bool:
        return root["is_archived"] if isinstance(root, dict) else root.is_archived

    @strawberry.field
    def registrationsCount(self, root) -> int:
        return root.get("registrationsCount", 0) if isinstance(root, dict) else 0

    @strawberry.field
    def imageUrl(self, root) -> typing.Optional[str]:
        return root.get("imageUrl") if isinstance(root, dict) else root.imageUrl

    @strawberry.field
    def startDate(self, root) -> datetime:
        return root["start_date"] if isinstance(root, dict) else root.start_date

    @strawberry.field
    def endDate(self, root) -> datetime:
        return root["end_date"] if isinstance(root, dict) else root.end_date

    @strawberry.field
    def venue(self, info: Info, root: EventModel) -> Optional[VenueType]:
        """Resolves the full Venue object from the venue_id stored on the event."""
        db = info.context.db
        venue_id = root.get("venue_id") if isinstance(root, dict) else root.venue_id
        if venue_id:
            return crud.venue.get(db, id=venue_id)
        return None

    @strawberry.field
    def isPublic(self, root) -> bool:
        return root["is_public"] if isinstance(root, dict) else root.is_public

    @strawberry.field
    def createdAt(self, root) -> datetime:
        return root["createdAt"] if isinstance(root, dict) else root.createdAt

    @strawberry.field
    def updatedAt(self, root) -> datetime:
        return root["updatedAt"] if isinstance(root, dict) else root.updatedAt

    # ==== VIRTUAL EVENT SUPPORT (Phase 1) ====

    @strawberry.field
    def eventType(self, root) -> EventTypeEnum:
        """Event type: IN_PERSON, VIRTUAL, or HYBRID."""
        event_type_value = root.get("event_type", "IN_PERSON") if isinstance(root, dict) else getattr(root, "event_type", "IN_PERSON")
        return EventTypeEnum(event_type_value)

    @strawberry.field
    def virtualSettings(self, root) -> Optional[VirtualSettingsType]:
        """Virtual event configuration settings."""
        settings = root.get("virtual_settings") if isinstance(root, dict) else getattr(root, "virtual_settings", None)
        if not settings:
            return None
        # Parse JSONB to VirtualSettingsType
        return VirtualSettingsType(
            streamingProvider=settings.get("streaming_provider"),
            streamingUrl=settings.get("streaming_url"),
            recordingEnabled=settings.get("recording_enabled", True),
            autoCaptions=settings.get("auto_captions", False),
            timezoneDisplay=settings.get("timezone_display"),
            lobbyEnabled=settings.get("lobby_enabled", False),
            lobbyVideoUrl=settings.get("lobby_video_url"),
            maxConcurrentViewers=settings.get("max_concurrent_viewers"),
            geoRestrictions=settings.get("geo_restrictions")
        )


# The rest of the types are correct.
@strawberry.type
class SessionType:
    id: str
    title: str

    # Use resolvers to map snake_case model attributes to camelCase API fields
    @strawberry.field
    def eventId(self, root: SessionModel) -> str:
        return root.event_id

    @strawberry.field
    def startTime(self, root: SessionModel) -> datetime:
        return root.start_time

    @strawberry.field
    def endTime(self, root: SessionModel) -> datetime:
        return root.end_time

    @strawberry.field
    def isArchived(self, root: SessionModel) -> bool:
        return root.is_archived

    @strawberry.field
    def chatEnabled(self, root: SessionModel) -> bool:
        """Whether chat is enabled for this session."""
        return root.chat_enabled

    @strawberry.field
    def qaEnabled(self, root: SessionModel) -> bool:
        """Whether Q&A is enabled for this session."""
        return root.qa_enabled

    @strawberry.field
    def chatOpen(self, root: SessionModel) -> bool:
        """Whether chat is currently open for this session (runtime control)."""
        return root.chat_open

    @strawberry.field
    def qaOpen(self, root: SessionModel) -> bool:
        """Whether Q&A is currently open for this session (runtime control)."""
        return root.qa_open

    @strawberry.field
    def pollsEnabled(self, root: SessionModel) -> bool:
        """Whether polls are enabled for this session."""
        return root.polls_enabled

    @strawberry.field
    def pollsOpen(self, root: SessionModel) -> bool:
        """Whether polls are currently open for this session (runtime control)."""
        return root.polls_open

    # The 'speakers' relationship should also be explicitly resolved for safety
    @strawberry.field
    def speakers(self, root: SessionModel) -> typing.List[SpeakerType]:
        return root.speakers

    @strawberry.field
    def status(self, root: SessionModel) -> str:
        """
        Computed status field based on current time:
        - UPCOMING: start_time > now
        - LIVE: start_time <= now <= end_time
        - ENDED: end_time < now
        """
        now = datetime.now(root.start_time.tzinfo)
        if now < root.start_time:
            return "UPCOMING"
        if now <= root.end_time:
            return "LIVE"
        return "ENDED"

    # ==== VIRTUAL SESSION SUPPORT (Phase 1) ====

    @strawberry.field
    def sessionType(self, root: SessionModel) -> SessionTypeEnum:
        """Session type: MAINSTAGE, BREAKOUT, WORKSHOP, NETWORKING, EXPO."""
        session_type_value = getattr(root, "session_type", "MAINSTAGE")
        return SessionTypeEnum(session_type_value)

    @strawberry.field
    def virtualRoomId(self, root: SessionModel) -> Optional[str]:
        """External virtual room identifier."""
        return getattr(root, "virtual_room_id", None)

    @strawberry.field
    def streamingUrl(self, root: SessionModel) -> Optional[str]:
        """Live stream URL for virtual sessions."""
        return getattr(root, "streaming_url", None)

    @strawberry.field
    def recordingUrl(self, root: SessionModel) -> Optional[str]:
        """Recording URL for on-demand playback."""
        return getattr(root, "recording_url", None)

    @strawberry.field
    def isRecordable(self, root: SessionModel) -> bool:
        """Whether session can be recorded."""
        return getattr(root, "is_recordable", True)

    @strawberry.field
    def requiresCamera(self, root: SessionModel) -> bool:
        """Whether attendees need camera access."""
        return getattr(root, "requires_camera", False)

    @strawberry.field
    def requiresMicrophone(self, root: SessionModel) -> bool:
        """Whether attendees need microphone access."""
        return getattr(root, "requires_microphone", False)

    @strawberry.field
    def maxParticipants(self, root: SessionModel) -> Optional[int]:
        """Max participants for interactive sessions."""
        return getattr(root, "max_participants", None)

    @strawberry.field
    def broadcastOnly(self, root: SessionModel) -> bool:
        """View-only session (no attendee A/V)."""
        return getattr(root, "broadcast_only", True)

    # ==== GREEN ROOM / BACKSTAGE SUPPORT (P1) ====

    @strawberry.field
    def greenRoomEnabled(self, root: SessionModel) -> bool:
        """Whether green room is enabled for speakers."""
        return getattr(root, "green_room_enabled", True)

    @strawberry.field
    def greenRoomOpensMinutesBefore(self, root: SessionModel) -> int:
        """Minutes before session that green room opens."""
        return getattr(root, "green_room_opens_minutes_before", 15)

    @strawberry.field
    def greenRoomNotes(self, root: SessionModel) -> Optional[str]:
        """Producer notes visible in green room."""
        return getattr(root, "green_room_notes", None)

    @strawberry.field
    def greenRoomOpen(self, root: SessionModel) -> bool:
        """Computed: Whether green room is currently open based on time."""
        if not getattr(root, "green_room_enabled", True):
            return False
        minutes_before = getattr(root, "green_room_opens_minutes_before", 15)
        open_time = root.start_time - timedelta(minutes=minutes_before)
        now = datetime.now(root.start_time.tzinfo)
        # Green room is open from X minutes before start until session ends
        return open_time <= now <= root.end_time


@strawberry.type
class RegistrationType:
    id: str
    status: str

    @strawberry.field
    def ticketCode(self, root: RegistrationModel) -> str:
        return root.ticket_code

    @strawberry.field
    def checkedInAt(self, root: RegistrationModel) -> typing.Optional[datetime]:
        return root.checked_in_at

    @strawberry.field
    def guestEmail(self, root: RegistrationModel) -> typing.Optional[str]:
        return root.guest_email

    @strawberry.field
    def guestName(self, root: RegistrationModel) -> typing.Optional[str]:
        return root.guest_name

    @strawberry.field
    def user(self, root: RegistrationModel) -> typing.Optional["User"]:
        if root.user_id:
            return User(id=root.user_id)
        return None


@strawberry.type
class BlueprintType:
    id: str
    organization_id: str
    name: str
    description: Optional[str]

    @strawberry.field
    def template(self, root) -> str:
        # The template is stored as JSONB, so we serialize it to a string for GraphQL
        return json.dumps(root.template)


@strawberry.type
class DomainEventType:
    id: str
    timestamp: datetime

    @strawberry.field
    def eventType(self, root) -> str:
        # Maps the 'event_type' from the database to 'eventType' in GraphQL
        return root.event_type

    @strawberry.field
    def userId(self, root) -> Optional[str]:
        # Maps the 'user_id' from the database to 'userId' in GraphQL
        return root.user_id

    @strawberry.field
    def data(self, root) -> Optional[str]:
        # The `data` field is JSONB, so we serialize it to a string for GraphQL
        if root.data:
            return json.dumps(root.data)
        return None


# --- PUBLIC EVENT TYPES (No authentication required) ---

@strawberry.type
class PublicEventType:
    """
    A simplified event type for public discovery endpoints.
    Contains only publicly-safe information.
    """

    @strawberry.field
    def id(self, root) -> str:
        return root.id

    @strawberry.field
    def name(self, root) -> str:
        return root.name

    @strawberry.field
    def description(self, root) -> Optional[str]:
        return root.description

    @strawberry.field
    def startDate(self, root) -> datetime:
        return root.start_date

    @strawberry.field
    def endDate(self, root) -> datetime:
        return root.end_date

    @strawberry.field
    def imageUrl(self, root) -> Optional[str]:
        return root.imageUrl

    @strawberry.field
    def venue(self, info: Info, root) -> Optional[VenueType]:
        """Resolves the full Venue object from the venue relationship."""
        # The venue is already eager-loaded by the query
        if hasattr(root, 'venue') and root.venue:
            return root.venue
        return None


@strawberry.type
class PublicEventsResponse:
    """Response type for the publicEvents query with pagination info."""
    totalCount: int
    events: typing.List[PublicEventType]


# --- ATTENDEE REGISTRATION TYPES ---

@strawberry.type
class MyRegistrationEventType:
    """
    Event details returned within an attendee's registration.
    Contains publicly-safe event information.
    """

    @strawberry.field
    def id(self, root) -> str:
        return root.id

    @strawberry.field
    def name(self, root) -> str:
        return root.name

    @strawberry.field
    def description(self, root) -> Optional[str]:
        return root.description

    @strawberry.field
    def startDate(self, root) -> datetime:
        return root.start_date

    @strawberry.field
    def endDate(self, root) -> datetime:
        return root.end_date

    @strawberry.field
    def status(self, root) -> str:
        return root.status

    @strawberry.field
    def imageUrl(self, root) -> Optional[str]:
        return root.imageUrl

    @strawberry.field
    def venue(self, info: Info, root) -> Optional[VenueType]:
        """Resolves the full Venue object from the venue relationship."""
        db = info.context.db
        if root.venue_id:
            return crud.venue.get(db, id=root.venue_id)
        return None


@strawberry.type
class MyRegistrationType:
    """
    Registration type for attendee dashboard queries.
    Includes nested event information.
    """
    id: str
    status: str

    @strawberry.field
    def ticketCode(self, root: RegistrationModel) -> str:
        return root.ticket_code

    @strawberry.field
    def checkedInAt(self, root: RegistrationModel) -> Optional[datetime]:
        return root.checked_in_at

    @strawberry.field
    def createdAt(self, root: RegistrationModel) -> Optional[datetime]:
        # Registration model doesn't have createdAt, return None for now
        return None

    @strawberry.field
    def event(self, root: RegistrationModel) -> Optional[MyRegistrationEventType]:
        """Returns the event associated with this registration."""
        if hasattr(root, 'event') and root.event:
            return root.event
        return None


# --- DASHBOARD STATS TYPES ---

@strawberry.type
class OrganizationDashboardStatsType:
    """
    Dashboard statistics for an organization.
    Provides key metrics for the organizer dashboard.
    """
    totalAttendees: int
    totalAttendeesChange: Optional[float] = None  # % change from previous period
    activeSessions: int
    activeSessionsChange: Optional[int] = None
    avgEngagementRate: float
    avgEngagementChange: Optional[float] = None
    totalEvents: int
    totalEventsChange: Optional[int] = None


@strawberry.type
class WeeklyAttendanceDataPoint:
    """A single data point for weekly attendance chart."""
    label: str  # "Mon", "Tue", etc.
    date: str   # ISO date string
    value: int  # Number of registrations/check-ins that day


@strawberry.type
class WeeklyAttendanceResponse:
    """Response type for weekly attendance query."""
    data: typing.List[WeeklyAttendanceDataPoint]


@strawberry.type
class EngagementTrendDataPoint:
    """A single data point for engagement trend sparkline."""
    period: str  # Period identifier (e.g., date or week label)
    value: float  # Engagement score for that period (0-100)


@strawberry.type
class EngagementTrendResponse:
    """Response type for engagement trend query."""
    data: typing.List[EngagementTrendDataPoint]


@strawberry.type
class EngagementBreakdownType:
    """
    Detailed breakdown of engagement metrics.
    Shows participation rates for Q&A, polls, and chat.
    """
    # Q&A participation
    qaParticipation: float  # Percentage (0-100)
    qaParticipationCount: int  # Absolute number of users who participated
    qaTotal: int  # Total possible participants

    # Poll responses
    pollResponseRate: float  # Percentage (0-100)
    pollResponseCount: int
    pollTotal: int

    # Chat activity
    chatActivityRate: float  # Percentage (0-100)
    chatMessageCount: int
    chatParticipants: int
    chatTotal: int


# --- MONETIZATION TYPES ---

@strawberry.type
class AdType:
    id: str
    organization_id: str
    event_id: Optional[str]
    name: str
    content_type: str
    media_url: str
    click_url: str
    is_archived: bool

    @strawberry.field
    def displayDuration(self, root) -> Optional[int]:
        """Display duration in seconds from the model."""
        return root.display_duration_seconds if hasattr(root, 'display_duration_seconds') else None

    @strawberry.field
    def weight(self, root) -> Optional[int]:
        """Ad weight for rotation priority."""
        return root.weight if hasattr(root, 'weight') else None


@strawberry.type
class InventoryStatusType:
    """Inventory status for an offer."""
    total: Optional[int]  # null = unlimited
    available: int
    sold: int
    reserved: int


@strawberry.type
class OfferType:
    id: str
    organization_id: str
    event_id: str
    title: str
    description: Optional[str]
    price: float
    original_price: Optional[float]
    currency: str
    offer_type: str
    image_url: Optional[str]
    expires_at: Optional[datetime]
    is_archived: bool

    # Inventory
    @strawberry.field
    def inventory(self, root) -> InventoryStatusType:
        """Returns inventory status."""
        inv = root.get("inventory") if isinstance(root, dict) else getattr(root, "inventory", None)
        if inv:
            return InventoryStatusType(
                total=inv.get("total") if isinstance(inv, dict) else getattr(inv, "total", None),
                available=inv.get("available", 0) if isinstance(inv, dict) else getattr(inv, "available", 0),
                sold=inv.get("sold", 0) if isinstance(inv, dict) else getattr(inv, "sold", 0),
                reserved=inv.get("reserved", 0) if isinstance(inv, dict) else getattr(inv, "reserved", 0)
            )
        return InventoryStatusType(total=None, available=0, sold=0, reserved=0)

    # Targeting & Placement
    @strawberry.field
    def placement(self, root) -> str:
        """Placement type for the offer."""
        return root.get("placement", "IN_EVENT") if isinstance(root, dict) else getattr(root, "placement", "IN_EVENT")

    @strawberry.field
    def targetSessions(self, root) -> typing.List[str]:
        """Target session IDs."""
        return root.get("target_sessions", []) if isinstance(root, dict) else getattr(root, "target_sessions", [])

    @strawberry.field
    def targetTicketTiers(self, root) -> typing.List[str]:
        """Target ticket tier IDs."""
        return root.get("target_ticket_tiers", []) if isinstance(root, dict) else getattr(root, "target_ticket_tiers", [])

    # Stripe
    @strawberry.field
    def stripePriceId(self, root) -> Optional[str]:
        """Stripe price ID for payment integration."""
        return root.get("stripe_price_id") if isinstance(root, dict) else getattr(root, "stripe_price_id", None)

    # Scheduling
    @strawberry.field
    def startsAt(self, root) -> Optional[datetime]:
        """Offer start time."""
        return root.get("starts_at") if isinstance(root, dict) else getattr(root, "starts_at", None)

    # Status
    @strawberry.field
    def isActive(self, root) -> bool:
        """Whether the offer is active."""
        return root.get("is_active", False) if isinstance(root, dict) else getattr(root, "is_active", False)


@strawberry.type
class DigitalContentType:
    """Digital content delivered with offer purchase."""
    downloadUrl: Optional[str]
    accessCode: Optional[str]


@strawberry.type
class OfferPurchaseType:
    """A user's purchased offer."""
    id: str
    offer: Optional[OfferType]
    quantity: int
    unitPrice: float
    totalPrice: float
    currency: str
    fulfillmentStatus: str
    fulfillmentType: Optional[str]
    digitalContent: Optional[DigitalContentType]
    trackingNumber: Optional[str]
    purchasedAt: Optional[str]
    fulfilledAt: Optional[str]


@strawberry.type
class PlatformStatsType:
    """Public platform statistics for marketing display."""
    totalEvents: int
    totalAttendees: int
    totalOrganizations: int
    uptimePercentage: float


# ==================== Monetization Analytics Types ====================

@strawberry.type
class RevenueDayType:
    """Revenue for a single day."""
    date: str
    amount: float


@strawberry.type
class RevenueAnalyticsType:
    """Revenue analytics breakdown."""
    total: float
    fromOffers: float
    fromAds: float
    byDay: typing.List[RevenueDayType]


@strawberry.type
class OfferPerformerType:
    """Top performing offer."""
    offerId: str
    title: str
    revenue: float
    conversions: int


@strawberry.type
class OffersAnalyticsType:
    """Offers analytics breakdown."""
    totalViews: int
    totalPurchases: int
    conversionRate: float
    averageOrderValue: float
    topPerformers: typing.List[OfferPerformerType]


@strawberry.type
class AdPerformerType:
    """Individual ad performance metrics."""
    adId: str
    name: str
    impressions: int
    clicks: int
    ctr: float
    isArchived: bool = False  # Indicates if ad was deleted/archived
    contentType: typing.Optional[str] = None  # BANNER, VIDEO, etc.


@strawberry.type
class AdsAnalyticsType:
    """Ads analytics breakdown with enhanced metrics."""
    totalImpressions: int
    totalClicks: int
    averageCTR: float
    activeAdsCount: int = 0  # Number of active (non-archived) ads
    archivedAdsCount: int = 0  # Number of archived ads (for historical reference)
    topPerformers: typing.List[AdPerformerType]
    # All ads with their individual metrics (not just top performers)
    allAdsPerformance: typing.List[AdPerformerType] = strawberry.field(default_factory=list)


@strawberry.type
class WaitlistAnalyticsSummaryType:
    """Waitlist analytics summary."""
    totalJoins: int
    offersIssued: int
    acceptanceRate: float
    averageWaitTimeMinutes: float


@strawberry.type
class MonetizationAnalyticsType:
    """Comprehensive monetization analytics."""
    revenue: RevenueAnalyticsType
    offers: OffersAnalyticsType
    ads: AdsAnalyticsType
    waitlist: WaitlistAnalyticsSummaryType


# ==================== Virtual Attendance Types ====================

@strawberry.type
class VirtualAttendanceType:
    """
    Tracks virtual session attendance for analytics.
    Each record represents a viewing session - when an attendee
    joins and leaves a virtual session.
    """
    id: str
    userId: str
    sessionId: str
    eventId: str
    joinedAt: datetime
    leftAt: Optional[datetime]
    watchDurationSeconds: Optional[int]
    deviceType: Optional[str]


@strawberry.type
class VirtualAttendanceStatsType:
    """
    Aggregate statistics for virtual attendance on a session.
    """
    sessionId: str
    totalViews: int
    uniqueViewers: int
    currentViewers: int
    avgWatchDurationSeconds: float
    peakViewers: int


@strawberry.type
class EventVirtualAttendanceStatsType:
    """
    Aggregate statistics for virtual attendance across an event.
    """
    eventId: str
    totalViews: int
    uniqueViewers: int
    currentViewers: int
    avgWatchDurationSeconds: float
    sessionStats: typing.List[VirtualAttendanceStatsType]


@strawberry.type
class JoinVirtualSessionResponse:
    """Response when a user joins a virtual session."""
    success: bool
    attendance: Optional[VirtualAttendanceType]
    message: Optional[str]


@strawberry.type
class LeaveVirtualSessionResponse:
    """Response when a user leaves a virtual session."""
    success: bool
    attendance: Optional[VirtualAttendanceType]
    watchDurationSeconds: Optional[int]
    message: Optional[str]