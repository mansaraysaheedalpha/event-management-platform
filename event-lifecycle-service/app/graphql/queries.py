# app/graphql/queries.py

import strawberry
from typing import List
from strawberry.types import Info
from fastapi import HTTPException
from .. import crud
from .types import EventType

# Make sure the debug print statement from our test is removed


@strawberry.type
class Query:
    @strawberry.field
    def event(self, id: str, info: Info) -> EventType:
        db = info.context.db
        event = crud.event.get(db, id=id)
        if not event:
            raise HTTPException(status_code=404, detail=f"Event with id {id} not found")
        return event

    @strawberry.field
    def events_by_organization(self, info: Info) -> List[EventType]:
        if not info.context.user or not info.context.user.get("orgId"):
            raise HTTPException(
                status_code=403, detail="Not authorized or orgId missing from context"
            )
        db = info.context.db
        org_id = info.context.user["orgId"]
        events = crud.event.get_multi_by_organization(db, org_id=org_id)
        return events
