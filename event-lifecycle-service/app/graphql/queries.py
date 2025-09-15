# event-lifecycle-service/app/graphql/queries.py

import strawberry
from typing import List
from strawberry.types import Info
from fastapi import HTTPException
from .. import crud
from .types import EventType, SpeakerType, SessionType, RegistrationType


@strawberry.type
class Query:
    @strawberry.field
    def event(
        self, id: strawberry.ID, info: Info
    ) -> EventType:  # ✅ THE FIX: Changed id: str to id: strawberry.ID
        """Fetches a single event by its GraphQL ID."""
        db = info.context.db

        # The CRUD function expects a string, so we cast the strawberry.ID
        event_id = str(id)

        event = crud.event.get(db, id=event_id)
        if not event:
            raise HTTPException(
                status_code=404, detail=f"Event with id {event_id} not found"
            )
        return event

    @strawberry.field
    def eventsByOrganization(self, info: Info) -> List[EventType]:
        if not info.context.user or not info.context.user.get("orgId"):
            raise HTTPException(
                status_code=403, detail="Not authorized or orgId missing from context"
            )
        db = info.context.db
        org_id = info.context.user["orgId"]
        events = crud.event.get_multi_by_organization(db, org_id=org_id)
        return events

    @strawberry.field
    def organizationSpeakers(self, info: Info) -> List[SpeakerType]:
        if not info.context.user or not info.context.user.get("orgId"):
            raise HTTPException(status_code=403, detail="Not authorized")
        db = info.context.db
        org_id = info.context.user["orgId"]
        return crud.speaker.get_multi_by_organization(db, org_id=org_id)

    @strawberry.field
    def sessionsByEvent(self, eventId: strawberry.ID, info: Info) -> List[SessionType]:
        if not info.context.user or not info.context.user.get("orgId"):
            raise HTTPException(status_code=403, detail="Not authorized")
        db = info.context.db
        return crud.session.get_multi_by_event(db, event_id=str(eventId))

    @strawberry.field
    def registrationsByEvent(
        self, eventId: strawberry.ID, info: Info
    ) -> List[RegistrationType]:
        if not info.context.user or not info.context.user.get("orgId"):
            raise HTTPException(status_code=403, detail="Not authorized")
        db = info.context.db
        return crud.registration.get_multi_by_event(db, event_id=str(eventId))
