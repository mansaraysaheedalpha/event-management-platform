# app/graphql/types.py
import strawberry
import typing
from datetime import datetime
from ..models.event import Event as EventModel
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
    first_name: str = strawberry.federation.field(external=True)
    last_name: str = strawberry.federation.field(external=True)


@strawberry.type
class SpeakerType:
    id: str
    organization_id: str
    name: str
    bio: typing.Optional[str]
    expertise: typing.Optional[list[str]]
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
    def venueId(self, root) -> typing.Optional[str]:
        return root.get("venue_id") if isinstance(root, dict) else root.venue_id

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

    # The 'speakers' relationship should also be explicitly resolved for safety
    @strawberry.field
    def speakers(self, root: SessionModel) -> typing.List[SpeakerType]:
        return root.speakers


# ------------------------------------

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
