# app/graphql/types.py
import strawberry
import typing 
from typing import Optional
import json
from datetime import datetime
from ..models.event import Event as EventModel
from .. import crud
from strawberry.types import Info
from ..models.venue import Venue as VenueModel
from ..models.registration import Registration as RegistrationModel
from ..models.session import Session as SessionModel


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

    # --- THIS IS THE NEWLY ADDED FIELD ---
    @strawberry.field
    def owner_id(self, root) -> str:
        return root["owner_id"] if isinstance(root, dict) else root.owner_id

    # ------------------------------------

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