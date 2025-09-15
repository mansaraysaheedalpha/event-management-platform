# event-lifecycle-service/app/graphql/types.py

import strawberry
import typing
from datetime import datetime
from ..models.event import Event as EventModel
from ..models.registration import Registration as RegistrationModel


# This federated UserType is correct.
@strawberry.federation.type(keys=["id"], extend=True)
class UserType:
    id: str = strawberry.federation.field(external=True)


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

    # These fields have a camelCase name in the schema but snake_case in the model.
    # We must provide custom resolvers for each of them.
    @strawberry.field
    def startDate(self, root: EventModel) -> datetime:
        return root.start_date

    @strawberry.field
    def endDate(self, root: EventModel) -> datetime:
        return root.end_date

    @strawberry.field
    def venueId(self, root: EventModel) -> typing.Optional[str]:
        return root.venue_id

    @strawberry.field
    def isPublic(self, root: EventModel) -> bool:
        return root.is_public

    @strawberry.field
    def createdAt(self, root: EventModel) -> datetime:
        return root.createdAt  # This one was already camelCase in the model

    @strawberry.field
    def updatedAt(self, root: EventModel) -> datetime:
        return root.updatedAt  # This one was also camelCase


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
    def user(self, root: RegistrationModel) -> typing.Optional[UserType]:
        if root.user_id:
            return UserType(id=root.user_id)
        return None
