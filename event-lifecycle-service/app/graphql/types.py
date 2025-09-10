# app/graphql/types.py
import strawberry
import typing
import uuid
from datetime import datetime

@strawberry.federation.type(keys=["id"], extend=True)
class UserType:
    id: str = strawberry.federation.field(external=True)

@strawberry.type
class EventType:
    id: str
    organization_id: str
    name: str
    version: int
    description: typing.Optional[str]
    status: str
    start_date: datetime
    end_date: datetime
    venue_id: typing.Optional[str]
    is_public: bool
    is_archived: bool
    createdAt: datetime
    updatedAt: datetime

@strawberry.type
class VenueType:
    id: str
    organization_id: str
    name: str
    address: typing.Optional[str]
    is_archived: str

@strawberry.type
class SessionType:
    id: str
    event_id: str
    title: str
    start_time: datetime
    end_time: datetime
    is_archived: bool
    speakers: typing.List['SpeakerType']

@strawberry.type
class SpeakerType:
    id: str
    organization_id: str
    name: str
    bio: typing.Optional[str]
    expertise: typing.Optional[typing.List[str]]
    is_archived: str
    sessions: typing.List['SessionType']
