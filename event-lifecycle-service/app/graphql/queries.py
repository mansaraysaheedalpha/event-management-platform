# event-lifecycle-service/app/graphql/queries.py

import strawberry
import typing
from typing import List
from strawberry.types import Info
from fastapi import HTTPException
from .. import crud
from .types import (
    EventType,
    SpeakerType,
    SessionType,
    RegistrationType,
    EventsPayload,
    EventStatsType,
)


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

        event_obj = crud.event.get(db, id=event_id)
        if not event_obj:
            raise HTTPException(
                status_code=404, detail=f"Event with id {event_id} not found"
            )

        # Manually construct a dictionary to match the format from the list query
        from ..crud import crud_registration

        registrations_count = crud_registration.registration.get_count_by_event(
            db, event_id=event_obj.id
        )

        event_dict = {
            c.name: getattr(event_obj, c.name) for c in event_obj.__table__.columns
        }
        event_dict["registrationsCount"] = registrations_count

        return event_dict

    @strawberry.field
    def eventsByOrganization(
        self,
        info: Info,
        search: typing.Optional[str] = None,
        status: typing.Optional[str] = None,
        sortBy: typing.Optional[str] = None,
        sortDirection: typing.Optional[str] = None,
        limit: typing.Optional[int] = 100,
        offset: typing.Optional[int] = 0,
    ) -> EventsPayload:
        if not info.context.user or not info.context.user.get("orgId"):
            raise HTTPException(
                status_code=403, detail="Not authorized or orgId missing from context"
            )
        db = info.context.db
        org_id = info.context.user["orgId"]
        payload_data = crud.event.get_multi_by_organization(
            db,
            org_id=org_id,
            search=search,
            status=status,
            sort_by=sortBy,
            sort_direction=sortDirection,
            skip=offset,
            limit=limit,
        )
        return EventsPayload(
            events=payload_data["events"], totalCount=payload_data["totalCount"]
        )

    @strawberry.field
    def eventStats(self, info: Info) -> EventStatsType:
        if not info.context.user or not info.context.user.get("orgId"):
            raise HTTPException(
                status_code=403, detail="Not authorized or orgId missing from context"
            )
        db = info.context.db
        org_id = info.context.user["orgId"]
        stats_data = crud.event.get_event_stats(db, org_id=org_id)
        return EventStatsType(
            totalEvents=stats_data["totalEvents"],
            upcomingEvents=stats_data["upcomingEvents"],
            upcomingRegistrations=stats_data["upcomingRegistrations"],
        )

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
