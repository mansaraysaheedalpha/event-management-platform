import strawberry
from strawberry.types import Info
from .types import EventType
from .. import crud
from ..schemas.event import EventCreate, EventUpdate
from typing import Optional

@strawberry.input
class EventCreateInput:
    name: str
    description: Optional[str]
    start_date: str
    end_date: str
    venue_id: Optional[str]

@strawberry.input
class EventUpdateInput:
    name: Optional[str] = None
    description: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    venue_id: Optional[str] = None
    is_public: Optional[bool] = None

@strawberry.type
class Mutation:
    @strawberry.mutation
    def create_event(self, event_in: EventCreateInput, org_id: str, user_id: str, info: Info) -> EventType:
        db = info.context.db
        event = crud.event.create_with_organization(db, obj_in=EventCreate(**event_in.__dict__), org_id=org_id, user_id=user_id)
        return event

    @strawberry.mutation
    def update_event(self, id: str, event_in: EventUpdateInput, user_id: str, info: Info) -> EventType:
        db = info.context.db
        db_obj = crud.event.get(db, id=id)
        event = crud.event.update(db, db_obj=db_obj, obj_in=EventUpdate(**event_in.__dict__), user_id=user_id)
        return event

    @strawberry.mutation
    def archive_event(self, id: str, user_id: str, info: Info) -> EventType:
        db = info.context.db
        event = crud.event.archive(db, id=id, user_id=user_id)
        return event
