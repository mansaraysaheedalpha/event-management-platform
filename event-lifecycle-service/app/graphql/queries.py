# app/graphql/queries.py
import strawberry
import typing
from typing import List, Optional
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
    VenueType,
    BlueprintType,
    DomainEventType,
)


@strawberry.type
class Query:
    @strawberry.field
    def event(self, id: strawberry.ID, info: Info) -> Optional[EventType]:
        db = info.context.db
        user = info.context.user
        event_id = str(id)
        event_obj = crud.event.get(db, id=event_id)
        if not event_obj:
            return None

        # --- NEW SECURITY CHECK ---
        # If the user is authenticated, they must belong to the same organization.
        if user and event_obj.organization_id != user.get("orgId"):
            return None

        # If the user is not authenticated, only show public, non-archived events.
        if not user and (not event_obj.is_public or event_obj.is_archived):
            return None
        # ------------------------

        from ..crud import crud_registration

        registrations_count = crud_registration.registration.get_count_by_event(
            db, event_id=event_obj.id
        )
        event_dict = {
            c.name: getattr(event_obj, c.name) for c in event_obj.__table__.columns
        }
        event_dict["registrationsCount"] = registrations_count
        return event_dict

    # --- ADD THIS NEW PUBLIC QUERY ---
    @strawberry.field
    def publicSessionsByEvent(
        self, eventId: strawberry.ID, info: Info
    ) -> List[SessionType]:
        """
        Publicly fetches sessions for a single event, but only if the event
        is published and not archived.
        """
        db = info.context.db
        event = crud.event.get(db, id=str(eventId))

        if not event or not event.is_public or event.is_archived:
            raise HTTPException(
                status_code=404, detail="Event not found or is not public"
            )

        return crud.session.get_multi_by_event(db, event_id=str(eventId))

    # -------------------------------
    @strawberry.field
    def eventsByOrganization(
        self,
        info: Info,
        search: typing.Optional[str] = None,
        status: typing.Optional[str] = None,
        sortBy: typing.Optional[str] = "start_date",
        sortDirection: typing.Optional[str] = "desc",
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
    def speaker(self, id: strawberry.ID, info: Info) -> Optional[SpeakerType]:
        user = info.context.user
        if not user or not user.get("orgId"):
            raise HTTPException(status_code=403, detail="Not authorized")
        db = info.context.db
        org_id = user["orgId"]
        speaker_obj = crud.speaker.get(db, id=str(id))
        if not speaker_obj or speaker_obj.organization_id != org_id:
            return None
        return speaker_obj

    @strawberry.field
    def sessionsByEvent(self, eventId: strawberry.ID, info: Info) -> List[SessionType]:
        user = info.context.user
        if not user or not user.get("orgId"):
            raise HTTPException(status_code=403, detail="Not authorized")
        db = info.context.db
        org_id = user["orgId"]

        # First, verify the user has access to this event
        event = crud.event.get(db, id=str(eventId))
        if not event or event.organization_id != org_id:
            raise HTTPException(status_code=404, detail="Event not found")

        return crud.session.get_multi_by_event(db, event_id=str(eventId))

    @strawberry.field
    def organizationVenues(self, info: Info) -> List[VenueType]:
        user = info.context.user
        if not user or not user.get("orgId"):
            raise HTTPException(status_code=403, detail="Not authorized")
        db = info.context.db
        org_id = user["orgId"]
        # Assuming get_multi_by_organization also filters out archived items
        return crud.venue.get_multi_by_organization(db, org_id=org_id)

    @strawberry.field
    def venue(self, id: strawberry.ID, info: Info) -> Optional[VenueType]:
        user = info.context.user
        if not user or not user.get("orgId"):
            raise HTTPException(status_code=403, detail="Not authorized")
        db = info.context.db
        org_id = user["orgId"]

        venue_obj = crud.venue.get(db, id=str(id))
        if not venue_obj or venue_obj.organization_id != org_id:
            return None

        return venue_obj

    @strawberry.field
    def registrationsByEvent(
        self, eventId: strawberry.ID, info: Info
    ) -> List[RegistrationType]:
        if not info.context.user or not info.context.user.get("orgId"):
            raise HTTPException(status_code=403, detail="Not authorized")
        db = info.context.db
        return crud.registration.get_multi_by_event(db, event_id=str(eventId))

    @strawberry.field
    def organizationBlueprints(self, info: Info) -> List[BlueprintType]:
        user = info.context.user
        if not user or not user.get("orgId"):
            raise HTTPException(status_code=403, detail="Not authorized")
        db = info.context.db
        org_id = user["orgId"]
        return crud.blueprint.get_multi_by_organization(db, org_id=org_id)

    @strawberry.field
    def eventHistory(self, eventId: strawberry.ID, info: Info) -> List[DomainEventType]:
        """
        Retrieves a chronological log of all domain events for a specific event.
        """
        user = info.context.user
        if not user or not user.get("orgId"):
            raise HTTPException(status_code=403, detail="Not authorized")

        db = info.context.db
        org_id = user["orgId"]

        # First, verify the user has access to this event
        event = crud.event.get(db, id=str(eventId))
        if not event or event.organization_id != org_id:
            raise HTTPException(status_code=404, detail="Event not found")

        return crud.domain_event.get_for_event(db, event_id=str(eventId))
