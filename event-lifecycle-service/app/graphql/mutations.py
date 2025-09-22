# event-lifecycle-service/app/graphql/mutations.py

import strawberry
from typing import Optional, List
from strawberry.types import Info
from fastapi import HTTPException
from .. import crud
from datetime import datetime
from ..schemas.event import EventCreate, EventUpdate
from ..schemas.session import SessionCreate
from ..schemas.registration import RegistrationCreate
from .types import EventType, SessionType, RegistrationType


@strawberry.input
class EventCreateInput:
    name: str
    description: Optional[str]
    startDate: str
    endDate: str
    venueId: Optional[str] = None


@strawberry.input
class EventUpdateInput:
    name: Optional[str] = None
    description: Optional[str] = None
    startDate: Optional[str] = None
    endDate: Optional[str] = None
    venueId: Optional[str] = None
    isPublic: Optional[bool] = None


@strawberry.input
class SessionCreateInput:
    eventId: str
    title: str
    sessionDate: str
    startTime: str
    endTime: str
    speakerIds: Optional[List[str]] = None


@strawberry.input
class RegistrationCreateInput:
    user_id: Optional[str] = None
    email: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None


@strawberry.type
class Mutation:
    @strawberry.mutation
    def createEvent(
        self, eventIn: EventCreateInput, info: Info
    ) -> EventType:  # Renamed to createEvent
        user = info.context.user
        if (
            not user or not user.get("orgId") or not user.get("sub")
        ):  # Check for user ID
            raise HTTPException(status_code=403, detail="Not authorized")

        db = info.context.db
        org_id = user["orgId"]
        user_id = user["sub"]  # Get user ID from token

        event_schema = EventCreate(
            owner_id=user_id,  # <-- PASS THE OWNER ID
            name=eventIn.name,
            description=eventIn.description,
            start_date=eventIn.startDate,
            end_date=eventIn.endDate,
            venue_id=eventIn.venueId,
        )

        event = crud.event.create_with_organization(
            db, obj_in=event_schema, org_id=org_id
        )
        return event

    @strawberry.mutation
    def createSession(self, sessionIn: SessionCreateInput, info: Info) -> SessionType:
        if not info.context.user or not info.context.user.get("orgId"):
            raise HTTPException(status_code=403, detail="Not authorized")

        db = info.context.db
        producer = info.context.producer  # <-- Get the producer from the context

        try:
            session_date_obj = datetime.fromisoformat(sessionIn.sessionDate).date()
            start_time_obj = datetime.strptime(sessionIn.startTime, "%H:%M").time()
            end_time_obj = datetime.strptime(sessionIn.endTime, "%H:%M").time()
            full_start_datetime = datetime.combine(session_date_obj, start_time_obj)
            full_end_datetime = datetime.combine(session_date_obj, end_time_obj)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail="Invalid date or time format. Use YYYY-MM-DD and HH:MM.",
            )

        session_schema = SessionCreate(
            title=sessionIn.title,
            start_time=full_start_datetime,
            end_time=full_end_datetime,
            speaker_ids=sessionIn.speakerIds,
        )

        return crud.session.create_with_event(
            db, obj_in=session_schema, event_id=sessionIn.eventId, producer=producer
        )

    @strawberry.mutation
    def create_registration(
        self, registrationIn: RegistrationCreateInput, eventId: str, info: Info
    ) -> RegistrationType:
        db = info.context.db

        is_guest_reg = registrationIn.email is not None
        is_user_reg = registrationIn.user_id is not None

        if is_guest_reg and is_user_reg:
            raise HTTPException(
                status_code=400,
                detail="Provide either user_id or guest details, not both.",
            )

        if not is_guest_reg and not is_user_reg:
            raise HTTPException(
                status_code=400,
                detail="Either user_id or guest details must be provided.",
            )

        if is_guest_reg and (
            not registrationIn.first_name or not registrationIn.last_name
        ):
            raise HTTPException(
                status_code=400,
                detail="Email, first name, and last name are required for guest registration.",
            )

        # Check if the event is public or if the user is authenticated
        event = crud.event.get(db, id=eventId)
        if not event:
            raise HTTPException(status_code=404, detail="Event not found")

        # Public events are open for guest registration.
        # Authenticated users can register for any event they have access to.
        user = info.context.get("user")
        if not event.is_public and not user:
            raise HTTPException(
                status_code=403,
                detail="You must be logged in to register for this private event.",
            )

        # If a user_id is provided, ensure it matches the authenticated user
        if registrationIn.user_id and (
            not user or user.get("sub") != registrationIn.user_id
        ):
            raise HTTPException(
                status_code=403,
                detail="Provided user_id does not match authenticated user.",
            )

        reg_schema = RegistrationCreate(
            user_id=registrationIn.user_id,
            email=registrationIn.email,
            first_name=registrationIn.first_name,
            last_name=registrationIn.last_name,
        )

        # Check for existing registration
        existing_reg = crud.registration.get_by_user_or_email(
            db,
            event_id=eventId,
            user_id=reg_schema.user_id,
            email=reg_schema.email,
        )
        if existing_reg:
            raise HTTPException(
                status_code=409,
                detail="A registration already exists for this user or email.",
            )

        return crud.registration.create_for_event(
            db, obj_in=reg_schema, event_id=eventId
        )

    @strawberry.mutation
    def updateEvent(self, id: str, eventIn: EventUpdateInput, info: Info) -> EventType: # Renamed to updateEvent
        user = info.context.user
        if not user or not user.get("sub"):
            raise HTTPException(status_code=403, detail="Not authorized")

        db = info.context.db
        user_id = user["sub"]
        db_obj = crud.event.get(db, id=id)

        if not db_obj:
            raise HTTPException(status_code=404, detail="Event not found")

        # --- THIS IS THE OWNERSHIP CHECK ---
        if db_obj.owner_id != user_id:
            raise HTTPException(status_code=403, detail="Not authorized to edit this event")
        # ------------------------------------

        update_data = {k: v for k, v in eventIn.__dict__.items() if v is not None}
        if "startDate" in update_data:
            update_data["start_date"] = update_data.pop("startDate")
        if "endDate" in update_data:
            update_data["end_date"] = update_data.pop("endDate")
        if "venueId" in update_data:
            update_data["venue_id"] = update_data.pop("venueId")
        if "isPublic" in update_data:
            update_data["is_public"] = update_data.pop("isPublic")

        update_schema = EventUpdate(**update_data)
        event = crud.event.update(db, db_obj=db_obj, obj_in=update_schema, user_id=user_id)
        return event

    @strawberry.mutation
    def archiveEvent(self, id: str, info: Info) -> EventType: # Renamed to archiveEvent
        user = info.context.user
        if not user or not user.get("sub"):
            raise HTTPException(status_code=403, detail="Not authorized")

        db = info.context.db
        user_id = user["sub"]
        db_obj = crud.event.get(db, id=id) # Get the event first to check ownership

        if not db_obj:
            raise HTTPException(status_code=404, detail="Event not found")

        # --- THIS IS THE OWNERSHIP CHECK ---
        if db_obj.owner_id != user_id:
            raise HTTPException(status_code=403, detail="Not authorized to archive this event")
        # ------------------------------------

        event = crud.event.archive(db, id=id, user_id=user_id)
        return event

    # --- ADD THIS NEW MUTATION ---
    @strawberry.mutation
    def restoreEvent(self, id: str, info: Info) -> EventType:
        user = info.context.user
        if not user or not user.get("sub"):
            raise HTTPException(status_code=403, detail="Not authorized")

        db = info.context.db
        user_id = user["sub"]
        db_obj = crud.event.get(db, id=id)

        if not db_obj:
            raise HTTPException(status_code=404, detail="Event not found")

        if db_obj.owner_id != user_id:
            raise HTTPException(
                status_code=403, detail="Not authorized to restore this event"
            )

        event = crud.event.restore(db, id=id, user_id=user_id)
        return event

    # -----------------------------
