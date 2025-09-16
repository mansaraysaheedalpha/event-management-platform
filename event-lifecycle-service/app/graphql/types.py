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
    totalRegistrations: int


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


# ✅ THIS IS THE DEFINITIVE FIX FOR THE EVENT TYPE
@strawberry.type
class EventType:
    # These fields match snake_case, so they work automatically.
    id: str
    organization_id: str
    name: str
    version: int
    description: typing.Optional[str]
    status: str
    is_archived: bool

    @strawberry.field
    def imageUrl(self, root: dict) -> typing.Optional[str]:
        return root["imageUrl"]

    @strawberry.field
    def registrationsCount(self, root: dict) -> int:
        # This value is pre-calculated and attached in the CRUD layer
        return root["registrationsCount"]

    # These fields have a camelCase name in the schema but snake_case in the model.
    # We must provide custom resolvers for each of them.
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
        return root["createdAt"]  # This one was already camelCase in the model

    @strawberry.field
    def updatedAt(self, root: dict) -> datetime:
        return root["updatedAt"]  # This one was also camelCase


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
    ticketCode: str
    checkedInAt: typing.Optional[datetime]
    guestEmail: typing.Optional[str]
    guestName: typing.Optional[str]

    @strawberry.field
    def user(self, root: RegistrationModel) -> typing.Optional["User"]:
        if root.user_id:
            return User(id=root.user_id)
        return None
