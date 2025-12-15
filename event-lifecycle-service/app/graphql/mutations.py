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
from ..schemas.venue import VenueCreate, VenueUpdate
from .types import EventType, SessionType, RegistrationType, SpeakerType, VenueType
from ..schemas.blueprint import BlueprintCreate  # <-- Import BlueprintCreate
from .types import EventType, BlueprintType


# --- All Input types defined at the top ---
@strawberry.input
class EventCreateInput:
    name: str
    description: Optional[str]
    startDate: str
    endDate: str
    venueId: Optional[str] = None
    imageUrl: Optional[str] = None


@strawberry.input
class EventUpdateInput:
    name: Optional[str] = None
    description: Optional[str] = None
    startDate: Optional[str] = None
    endDate: Optional[str] = None
    venueId: Optional[str] = None
    isPublic: Optional[bool] = None
    imageUrl: Optional[str] = None


@strawberry.input
class SessionCreateInput:
    eventId: str
    title: str
    sessionDate: str
    startTime: str
    endTime: str
    speakerIds: Optional[List[str]] = None
    chatEnabled: Optional[bool] = True  # Defaults to enabled
    qaEnabled: Optional[bool] = True  # Defaults to enabled
    pollsEnabled: Optional[bool] = True  # Defaults to enabled


@strawberry.input
class RegistrationCreateInput:
    userId: Optional[str] = None
    email: Optional[str] = None
    firstName: Optional[str] = None
    lastName: Optional[str] = None


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
    chatEnabled: Optional[bool] = None
    qaEnabled: Optional[bool] = None
    pollsEnabled: Optional[bool] = None


@strawberry.input
class VenueCreateInput:
    name: str
    address: Optional[str] = None


@strawberry.input
class VenueUpdateInput:
    name: Optional[str] = None
    address: Optional[str] = None


@strawberry.input
class BlueprintCreateInput:
    name: str
    description: Optional[str] = None
    eventId: str  # The ID of the event to use as a template


@strawberry.input
class InstantiateBlueprintInput:
    name: str
    startDate: str
    endDate: str


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
            imageUrl=eventIn.imageUrl,
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
        # imageUrl stays as-is since schema uses imageUrl (matches model column)

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
    def publishEvent(self, id: str, info: Info) -> EventType:
        user = info.context.user
        if not user or not user.get("sub"):
            raise HTTPException(status_code=403, detail="Not authorized")

        db = info.context.db
        user_id = user["sub"]
        user_role = user.get("role")

        event_to_publish = crud.event.get(db, id=id)
        if not event_to_publish:
            raise HTTPException(status_code=404, detail="Event not found")

        if event_to_publish.owner_id != user_id and user_role not in ["OWNER", "ADMIN"]:
            raise HTTPException(
                status_code=403, detail="Not authorized to publish this event"
            )

        if event_to_publish.status != "draft":
            raise HTTPException(
                status_code=409,
                detail=f"Cannot publish event with status '{event_to_publish.status}'",
            )

        return crud.event.publish(db, db_obj=event_to_publish, user_id=user_id)

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
            chat_enabled=sessionIn.chatEnabled if sessionIn.chatEnabled is not None else True,
            qa_enabled=sessionIn.qaEnabled if sessionIn.qaEnabled is not None else True,
            polls_enabled=sessionIn.pollsEnabled if sessionIn.pollsEnabled is not None else True,
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
        if "chatEnabled" in update_data:
            update_data["chat_enabled"] = update_data.pop("chatEnabled")
        if "qaEnabled" in update_data:
            update_data["qa_enabled"] = update_data.pop("qaEnabled")
        if "pollsEnabled" in update_data:
            update_data["polls_enabled"] = update_data.pop("pollsEnabled")
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
    def createVenue(self, venueIn: VenueCreateInput, info: Info) -> VenueType:
        user = info.context.user
        if not user or not user.get("orgId"):
            raise HTTPException(status_code=403, detail="Not authorized")
        db = info.context.db
        org_id = user["orgId"]
        venue_schema = VenueCreate(**venueIn.__dict__)
        return crud.venue.create_with_organization(
            db, obj_in=venue_schema, org_id=org_id
        )

    @strawberry.mutation
    def updateVenue(self, id: str, venueIn: VenueUpdateInput, info: Info) -> VenueType:
        user = info.context.user
        if not user or not user.get("orgId"):
            raise HTTPException(status_code=403, detail="Not authorized")
        db = info.context.db
        org_id = user["orgId"]
        venue = crud.venue.get(db, id=id)
        if not venue or venue.organization_id != org_id:
            raise HTTPException(status_code=404, detail="Venue not found")

        update_schema = VenueUpdate(
            **{k: v for k, v in venueIn.__dict__.items() if v is not None}
        )
        return crud.venue.update(db, db_obj=venue, obj_in=update_schema)

    @strawberry.mutation
    def archiveVenue(self, id: str, info: Info) -> VenueType:
        user = info.context.user
        if not user or not user.get("orgId"):
            raise HTTPException(status_code=403, detail="Not authorized")
        db = info.context.db
        org_id = user["orgId"]
        venue = crud.venue.get(db, id=id)
        if not venue or venue.organization_id != org_id:
            raise HTTPException(status_code=404, detail="Venue not found")

        return crud.venue.archive(db, id=id)

    @strawberry.mutation
    def createRegistration(
        self, registrationIn: RegistrationCreateInput, eventId: str, info: Info
    ) -> RegistrationType:
        db = info.context.db
        user = info.context.user

        is_guest_reg = registrationIn.email is not None

        # Determine the effective user_id:
        # 1. If userId provided, use it (will be validated below)
        # 2. If authenticated and not guest reg, auto-use JWT sub
        # 3. Otherwise None (guest registration)
        effective_user_id = registrationIn.userId
        if not effective_user_id and not is_guest_reg and user:
            # Auto-fill user_id from authenticated user for self-registration
            effective_user_id = user.get("sub")

        is_user_reg = effective_user_id is not None

        if is_guest_reg and is_user_reg:
            raise HTTPException(
                status_code=400,
                detail="Provide either user_id or guest details, not both.",
            )
        if not is_guest_reg and not is_user_reg:
            raise HTTPException(
                status_code=400,
                detail="You must be logged in or provide guest details to register.",
            )
        if is_guest_reg and (
            not registrationIn.firstName or not registrationIn.lastName
        ):
            raise HTTPException(
                status_code=400,
                detail="Email, first name, and last name are required for guest registration.",
            )

        event = crud.event.get(db, id=eventId)
        if not event:
            raise HTTPException(status_code=404, detail="Event not found")

        if not event.is_public and not user:
            raise HTTPException(
                status_code=403,
                detail="You must be logged in to register for this private event.",
            )

        # If userId was explicitly provided, validate it matches the authenticated user
        if registrationIn.userId and (
            not user or user.get("sub") != registrationIn.userId
        ):
            raise HTTPException(
                status_code=403,
                detail="Provided user_id does not match authenticated user.",
            )

        reg_schema = RegistrationCreate(
            user_id=effective_user_id,
            email=registrationIn.email,
            first_name=registrationIn.firstName,
            last_name=registrationIn.lastName,
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

        registration = crud.registration.create_for_event(
            db, obj_in=reg_schema, event_id=eventId
        )

        # Publish Kafka event for email notification
        producer = info.context.producer
        if producer:
            try:
                # Determine recipient email and name
                if is_guest_reg:
                    recipient_email = registrationIn.email
                    recipient_name = f"{registrationIn.firstName} {registrationIn.lastName}"
                else:
                    # For user registrations, get email from JWT
                    recipient_email = user.get("email") if user else None
                    recipient_name = user.get("name", "Attendee") if user else "Attendee"

                # Publish registration event to Kafka
                producer.send(
                    "registration.events.v1",
                    value={
                        "type": "REGISTRATION_CONFIRMED",
                        "registrationId": registration.id,
                        "ticketCode": registration.ticket_code,
                        "eventId": eventId,
                        "eventName": event.name,
                        "eventStartDate": event.start_date.isoformat(),
                        "eventEndDate": event.end_date.isoformat(),
                        "userId": effective_user_id,
                        "recipientEmail": recipient_email,
                        "recipientName": recipient_name,
                        "venueName": event.venue.name if event.venue else None,
                    },
                )
                print(f"[KAFKA] Published registration event for ticket: {registration.ticket_code}")
            except Exception as e:
                # Log but don't fail the registration if Kafka publish fails
                print(f"[KAFKA ERROR] Failed to publish registration event: {e}")

        return registration

    @strawberry.mutation
    def createBlueprint(
        self, blueprintIn: BlueprintCreateInput, info: Info
    ) -> BlueprintType:
        user = info.context.user
        if not user or not user.get("orgId"):
            raise HTTPException(status_code=403, detail="Not authorized")
        db = info.context.db
        org_id = user["orgId"]

        # Fetch the source event to create the template
        source_event = crud.event.get(db, id=blueprintIn.eventId)
        if not source_event or source_event.organization_id != org_id:
            raise HTTPException(status_code=404, detail="Source event not found")

        # Create the template object from the source event's data
        template_data = {
            "description": source_event.description,
            "is_public": source_event.is_public,
            # Add any other fields you want to save in the template
        }

        blueprint_schema = BlueprintCreate(
            name=blueprintIn.name,
            description=blueprintIn.description,
            template=template_data,
        )
        return crud.blueprint.create_with_organization(
            db, obj_in=blueprint_schema, org_id=org_id
        )

    @strawberry.mutation
    def instantiateBlueprint(
        self, id: str, blueprintIn: InstantiateBlueprintInput, info: Info
    ) -> EventType:
        user = info.context.user
        if not user or not user.get("orgId") or not user.get("sub"):
            raise HTTPException(status_code=403, detail="Not authorized")

        db = info.context.db
        org_id = user["orgId"]
        user_id = user["sub"]

        blueprint = crud.blueprint.get(db, id=id)
        if not blueprint or blueprint.organization_id != org_id:
            raise HTTPException(status_code=404, detail="Blueprint not found")

        # Combine blueprint template with new user-provided data
        event_data = {
            **blueprint.template,
            "owner_id": user_id,
            "name": blueprintIn.name,
            "start_date": blueprintIn.startDate,
            "end_date": blueprintIn.endDate,
        }

        event_schema = EventCreate(**event_data)
        return crud.event.create_with_organization(
            db, obj_in=event_schema, org_id=org_id
        )

    @strawberry.mutation
    def toggleSessionChat(self, id: str, open: bool, info: Info) -> SessionType:
        """
        Toggle the chat open/closed state for a session.
        Only works if chat is enabled for this session.
        """
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
                status_code=403, detail="Not authorized to modify this session"
            )
        if event.owner_id != user_id and user_role not in ["OWNER", "ADMIN"]:
            raise HTTPException(
                status_code=403, detail="Not authorized to modify this session"
            )

        if not session.chat_enabled:
            raise HTTPException(
                status_code=400, detail="Chat is disabled for this session"
            )

        # Update the chat_open state
        session.chat_open = open
        db.commit()
        db.refresh(session)

        # Publish to Redis for real-time broadcast
        from app.db.redis import redis_client
        import json
        redis_client.publish(
            "platform.sessions.chat.v1",
            json.dumps({
                "sessionId": id,
                "chatOpen": open,
                "eventId": session.event_id,
            })
        )

        return session

    @strawberry.mutation
    def toggleSessionQA(self, id: str, open: bool, info: Info) -> SessionType:
        """
        Toggle the Q&A open/closed state for a session.
        Only works if Q&A is enabled for this session.
        """
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
                status_code=403, detail="Not authorized to modify this session"
            )
        if event.owner_id != user_id and user_role not in ["OWNER", "ADMIN"]:
            raise HTTPException(
                status_code=403, detail="Not authorized to modify this session"
            )

        if not session.qa_enabled:
            raise HTTPException(
                status_code=400, detail="Q&A is disabled for this session"
            )

        # Update the qa_open state
        session.qa_open = open
        db.commit()
        db.refresh(session)

        # Publish to Redis for real-time broadcast
        from app.db.redis import redis_client
        import json
        redis_client.publish(
            "platform.sessions.qa.v1",
            json.dumps({
                "sessionId": id,
                "qaOpen": open,
                "eventId": session.event_id,
            })
        )

        return session

    @strawberry.mutation
    def toggleSessionPolls(self, id: str, open: bool, info: Info) -> SessionType:
        """
        Toggle the polls open/closed state for a session.
        Only works if polls are enabled for this session.
        """
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
                status_code=403, detail="Not authorized to modify this session"
            )
        if event.owner_id != user_id and user_role not in ["OWNER", "ADMIN"]:
            raise HTTPException(
                status_code=403, detail="Not authorized to modify this session"
            )

        if not session.polls_enabled:
            raise HTTPException(
                status_code=400, detail="Polls are disabled for this session"
            )

        # Update the polls_open state
        session.polls_open = open
        db.commit()
        db.refresh(session)

        # Publish to Redis for real-time broadcast
        from app.db.redis import redis_client
        import json
        redis_client.publish(
            "platform.sessions.polls.v1",
            json.dumps({
                "sessionId": id,
                "pollsOpen": open,
                "eventId": session.event_id,
            })
        )

        return session
