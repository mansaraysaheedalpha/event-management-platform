import strawberry
from typing import Optional, List
from strawberry.types import Info
from fastapi import HTTPException
from .. import crud
from datetime import datetime
from ..schemas.event import EventCreate, EventUpdate
from ..schemas.session import SessionCreate, SessionUpdate
from ..schemas.registration import RegistrationCreate
from ..schemas.speaker import SpeakerCreate, SpeakerUpdate
from .types import EventType, SessionType, RegistrationType, SpeakerType


# --- All Input types defined at the top ---
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


@strawberry.input
class SpeakerCreateInput:
    name: str
    bio: Optional[str] = None
    expertise: Optional[List[str]] = None


@strawberry.input
class SpeakerUpdateInput:
    name: Optional[str] = None
    bio: Optional[str] = None
    expertise: Optional[List[str]] = None


@strawberry.input
class SessionUpdateInput:
    title: Optional[str] = None
    startTime: Optional[str] = None
    endTime: Optional[str] = None
    speakerIds: Optional[List[str]] = None


# --- Main Mutation Class ---
@strawberry.type
class Mutation:
    @strawberry.mutation
    def createEvent(self, eventIn: EventCreateInput, info: Info) -> EventType:
        user = info.context.user
        if not user or not user.get("orgId") or not user.get("sub"):
            raise HTTPException(status_code=403, detail="Not authorized")
        db = info.context.db
        org_id = user["orgId"]
        user_id = user["sub"]
        event_schema = EventCreate(
            owner_id=user_id,
            name=eventIn.name,
            description=eventIn.description,
            start_date=eventIn.startDate,
            end_date=eventIn.endDate,
            venue_id=eventIn.venueId,
        )
        return crud.event.create_with_organization(
            db, obj_in=event_schema, org_id=org_id
        )

    @strawberry.mutation
    def updateEvent(self, id: str, eventIn: EventUpdateInput, info: Info) -> EventType:
        user = info.context.user
        if not user or not user.get("sub"):
            raise HTTPException(status_code=403, detail="Not authorized")
        db = info.context.db
        user_id = user["sub"]
        user_role = user.get("role")
        db_obj = crud.event.get(db, id=id)
        if not db_obj:
            raise HTTPException(status_code=404, detail="Event not found")
        if db_obj.owner_id != user_id and user_role not in ["OWNER", "ADMIN"]:
            raise HTTPException(
                status_code=403, detail="Not authorized to edit this event"
            )

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
        return crud.event.update(
            db, db_obj=db_obj, obj_in=update_schema, user_id=user_id
        )

    @strawberry.mutation
    def archiveEvent(self, id: str, info: Info) -> EventType:
        user = info.context.user
        if not user or not user.get("sub"):
            raise HTTPException(status_code=403, detail="Not authorized")
        db = info.context.db
        user_id = user["sub"]
        user_role = user.get("role")
        db_obj = crud.event.get(db, id=id)
        if not db_obj:
            raise HTTPException(status_code=404, detail="Event not found")
        if db_obj.owner_id != user_id and user_role not in ["OWNER", "ADMIN"]:
            raise HTTPException(
                status_code=403, detail="Not authorized to archive this event"
            )
        return crud.event.archive(db, id=id, user_id=user_id)

    @strawberry.mutation
    def restoreEvent(self, id: str, info: Info) -> EventType:
        user = info.context.user
        if not user or not user.get("sub"):
            raise HTTPException(status_code=403, detail="Not authorized")
        db = info.context.db
        user_id = user["sub"]
        user_role = user.get("role")
        db_obj = crud.event.get(db, id=id)
        if not db_obj:
            raise HTTPException(status_code=404, detail="Event not found")
        if db_obj.owner_id != user_id and user_role not in ["OWNER", "ADMIN"]:
            raise HTTPException(
                status_code=403, detail="Not authorized to archive this event"
            )
        return crud.event.restore(db, id=id, user_id=user_id)

    @strawberry.mutation
    def createSession(self, sessionIn: SessionCreateInput, info: Info) -> SessionType:
        if not info.context.user or not info.context.user.get("orgId"):
            raise HTTPException(status_code=403, detail="Not authorized")
        db = info.context.db
        producer = info.context.producer
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
    def updateSession(
        self, id: str, sessionIn: SessionUpdateInput, info: Info
    ) -> SessionType:
        user = info.context.user
        if not user or not user.get("orgId"):
            raise HTTPException(status_code=403, detail="Not authorized")
        db = info.context.db
        org_id = user["orgId"]
        user_role = user.get("role")
        user_id = user["sub"]
        session = crud.session.get(db, id=id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        event = crud.event.get(db, id=session.event_id)
        if not event or event.organization_id != org_id:
            raise HTTPException(
                status_code=403, detail="Not authorized to edit this session"
            )
        if event.owner_id != user_id and user_role not in ["OWNER", "ADMIN"]:
            raise HTTPException(
                status_code=403, detail="Not authorized to edit this session"
            )

        update_data = {k: v for k, v in sessionIn.__dict__.items() if v is not None}
        if "startTime" in update_data:
            update_data["start_time"] = datetime.fromisoformat(
                update_data.pop("startTime")
            )
        if "endTime" in update_data:
            update_data["end_time"] = datetime.fromisoformat(update_data.pop("endTime"))
        if "speakerIds" in update_data:
            update_data["speaker_ids"] = update_data.pop("speakerIds")
        update_schema = SessionUpdate(**update_data)
        return crud.session.update(db, db_obj=session, obj_in=update_schema)

    @strawberry.mutation
    def archiveSession(self, id: str, info: Info) -> SessionType:
        user = info.context.user
        if not user or not user.get("orgId"):
            raise HTTPException(status_code=403, detail="Not authorized")
        db = info.context.db
        org_id = user["orgId"]
        user_role = user.get("role")
        user_id = user["sub"]
        session = crud.session.get(db, id=id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        event = crud.event.get(db, id=session.event_id)
        if not event or event.organization_id != org_id:
            raise HTTPException(
                status_code=403, detail="Not authorized to archive this session"
            )
        if event.owner_id != user_id and user_role not in ["OWNER", "ADMIN"]:
            raise HTTPException(
                status_code=403, detail="Not authorized to archive this session"
            )
        return crud.session.archive(db, id=id)

    @strawberry.mutation
    def createSpeaker(self, speakerIn: SpeakerCreateInput, info: Info) -> SpeakerType:
        user = info.context.user
        if not user or not user.get("orgId"):
            raise HTTPException(status_code=403, detail="Not authorized")
        db = info.context.db
        org_id = user["orgId"]
        speaker_schema = SpeakerCreate(
            name=speakerIn.name, bio=speakerIn.bio, expertise=speakerIn.expertise
        )
        return crud.speaker.create_with_organization(
            db, obj_in=speaker_schema, org_id=org_id
        )

    @strawberry.mutation
    def updateSpeaker(
        self, id: str, speakerIn: SpeakerUpdateInput, info: Info
    ) -> SpeakerType:
        user = info.context.user
        if not user or not user.get("orgId"):
            raise HTTPException(status_code=403, detail="Not authorized")
        db = info.context.db
        org_id = user["orgId"]
        speaker = crud.speaker.get(db, id=id)
        if not speaker or speaker.organization_id != org_id:
            raise HTTPException(status_code=404, detail="Speaker not found")
        update_schema = SpeakerUpdate(
            **{k: v for k, v in speakerIn.__dict__.items() if v is not None}
        )
        return crud.speaker.update(db, db_obj=speaker, obj_in=update_schema)

    @strawberry.mutation
    def archiveSpeaker(self, id: str, info: Info) -> SpeakerType:
        user = info.context.user
        if not user or not user.get("orgId"):
            raise HTTPException(status_code=403, detail="Not authorized")
        db = info.context.db
        org_id = user["orgId"]
        speaker = crud.speaker.get(db, id=id)
        if not speaker or speaker.organization_id != org_id:
            raise HTTPException(status_code=404, detail="Speaker not found")
        return crud.speaker.archive(db, id=id)

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

        event = crud.event.get(db, id=eventId)
        if not event:
            raise HTTPException(status_code=404, detail="Event not found")

        user = info.context.get("user")
        if not event.is_public and not user:
            raise HTTPException(
                status_code=403,
                detail="You must be logged in to register for this private event.",
            )

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
