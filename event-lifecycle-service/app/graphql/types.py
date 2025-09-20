# event-lifecycle-service/app/graphql/types.py

import strawberry
import typing
from datetime import datetime
from strawberry.types import Info
from ..models.event import Event as EventModel
from ..models.registration import Registration as RegistrationModel


@strawberry.type
class EventsPayload:
    events: typing.List["EventType"]
    totalCount: int


@strawberry.type
class EventStatsType:
    totalEvents: int
    upcomingEvents: int
    upcomingRegistrations: int


# This federated User is correct.
@strawberry.federation.type(keys=["id"], extend=True)
class User:
    id: strawberry.ID = strawberry.federation.field(external=True)


# This SpeakerType is correct.
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
    def id(self, root: dict) -> str:
        return root["id"]

    @strawberry.field
    def organization_id(self, root: dict) -> str:
        return root["organization_id"]

    @strawberry.field
    def name(self, root: dict) -> str:
        return root["name"]

    @strawberry.field
    def version(self, root: dict) -> int:
        return root["version"]

    @strawberry.field
    def description(self, root: dict) -> typing.Optional[str]:
        return root["description"]

    @strawberry.field
    def status(self, root: dict) -> str:
        return root["status"]

    @strawberry.field
    def is_archived(self, root: dict) -> bool:
        return root["is_archived"]

    @strawberry.field
    def imageUrl(self, root: dict) -> typing.Optional[str]:
        return root["imageUrl"]

    @strawberry.field
    def registrationsCount(self, root: dict) -> int:
        return root["registrationsCount"]

    @strawberry.field
    def startDate(self, root: dict) -> datetime:
        return root["start_date"]

    @strawberry.field
    def endDate(self, root: dict) -> datetime:
        return root["end_date"]

    @strawberry.field
    def venueId(self, root: dict) -> typing.Optional[str]:
        return root["venue_id"]

    @strawberry.field
    def isPublic(self, root: dict) -> bool:
        return root["is_public"]

    @strawberry.field
    def createdAt(self, root: dict) -> datetime:
        return root["createdAt"]

    @strawberry.field
    def updatedAt(self, root: dict) -> datetime:
        return root["updatedAt"]


# The rest of the types are correct.
@strawberry.type
class SessionType:
    id: str
    event_id: str
    title: str
    startTime: datetime
    endTime: datetime
    is_archived: bool
    speakers: typing.List[SpeakerType]


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
