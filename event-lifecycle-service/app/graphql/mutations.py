# app/graphql/mutations.py

import strawberry
from typing import Optional
from strawberry.types import Info
from fastapi import HTTPException
from .. import crud
from ..schemas.event import EventCreate, EventUpdate
from .types import EventType


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
    def create_event(self, event_in: EventCreateInput, info: Info) -> EventType:
        if not info.context.user or not info.context.user.get("orgId"):
            raise HTTPException(status_code=403, detail="Not authorized")
        db = info.context.db
        org_id = info.context.user["orgId"]
        event = crud.event.create_with_organization(
            db, obj_in=EventCreate(**event_in.__dict__), org_id=org_id
        )
        return event

    @strawberry.mutation
    def update_event(
        self, id: str, event_in: EventUpdateInput, info: Info
    ) -> EventType:
        if not info.context.user or not info.context.user.get("sub"):
            raise HTTPException(status_code=403, detail="Not authorized")
        db = info.context.db
        user_id = info.context.user["sub"]
        db_obj = crud.event.get(db, id=id)
        if not db_obj:
            raise HTTPException(status_code=404, detail="Event not found")
        event = crud.event.update(
            db, db_obj=db_obj, obj_in=EventUpdate(**event_in.__dict__), user_id=user_id
        )
        return event

    @strawberry.mutation
    def archive_event(self, id: str, info: Info) -> EventType:
        if not info.context.user or not info.context.user.get("sub"):
            raise HTTPException(status_code=403, detail="Not authorized")
        db = info.context.db
        user_id = info.context.user["sub"]
        event = crud.event.archive(db, id=id, user_id=user_id)
        if not event:
            raise HTTPException(status_code=404, detail="Event not found")
        return event
