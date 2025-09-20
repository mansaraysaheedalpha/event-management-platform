# event-lifecycle-service/app/graphql/mutations.py

import strawberry
from typing import Optional, List
from strawberry.types import Info
from fastapi import HTTPException
from .. import crud
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
    startTime: str
    endTime: str
    speakerIds: Optional[List[str]] = None


@strawberry.input
class RegistrationCreateInput:
    email: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    user_id: Optional[str] = None


@strawberry.type
class Mutation:
    @strawberry.mutation
    def create_event(self, eventIn: EventCreateInput, info: Info) -> EventType:
        if not info.context.user or not info.context.user.get("orgId"):
            raise HTTPException(status_code=403, detail="Not authorized")

        db = info.context.db
        org_id = info.context.user["orgId"]

        event_schema = EventCreate(
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
    def create_session(self, sessionIn: SessionCreateInput, info: Info) -> SessionType:
        if not info.context.user or not info.context.user.get("orgId"):
            raise HTTPException(status_code=403, detail="Not authorized")
        db = info.context.db
        session_schema = SessionCreate(**sessionIn.__dict__)
        return crud.session.create_with_event(
            db, obj_in=session_schema, event_id=sessionIn.eventId
        )

    @strawberry.mutation
    def create_registration(
        self, registrationIn: RegistrationCreateInput, eventId: str, info: Info
    ) -> RegistrationType:
        db = info.context.db

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

        # If no user_id is provided, it's a guest registration.
        # Ensure email and name are provided for guest registrations.
        if not registrationIn.user_id:
            if (
                not registrationIn.email
                or not registrationIn.first_name
                or not registrationIn.last_name
            ):
                raise HTTPException(
                    status_code=400,
                    detail="Email, first name, and last name are required for guest registration.",
                )
            # Set the user_id to None for guest registrations
            registrationIn.user_id = None

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
    def update_event(self, id: str, eventIn: EventUpdateInput, info: Info) -> EventType:
        if not info.context.user or not info.context.user.get("sub"):
            raise HTTPException(status_code=403, detail="Not authorized")

        db = info.context.db
        user_id = info.context.user["sub"]
        db_obj = crud.event.get(db, id=id)

        if not db_obj:
            raise HTTPException(status_code=404, detail="Event not found")

        # Convert Strawberry input to Pydantic schema
        update_data = {k: v for k, v in eventIn.__dict__.items() if v is not None}
        # Manual mapping for consistency
        if "startDate" in update_data:
            update_data["start_date"] = update_data.pop("startDate")
        if "endDate" in update_data:
            update_data["end_date"] = update_data.pop("endDate")
        if "venueId" in update_data:
            update_data["venue_id"] = update_data.pop("venueId")
        if "isPublic" in update_data:
            update_data["is_public"] = update_data.pop("isPublic")

        update_schema = EventUpdate(**update_data)

        event = crud.event.update(
            db, db_obj=db_obj, obj_in=update_schema, user_id=user_id
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
