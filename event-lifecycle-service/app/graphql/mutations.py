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
from .payment_types import (
    CheckoutSessionType,
    OrderType,
    RefundType,
    TicketTypeType,
    PromoCodeType,
    CreateOrderInput,
    InitiateRefundInput,
    TicketTypeCreateInput,
    TicketTypeUpdateInput,
    PromoCodeCreateInput,
)
from .ticket_types import (
    TicketTypeFullType,
    TicketType as TicketGQLType,
    PromoCodeFullType,
    CreateTicketTypeInput as TktCreateTicketTypeInput,
    UpdateTicketTypeInput as TktUpdateTicketTypeInput,
    ReorderTicketTypesInput,
    CreatePromoCodeInput as TktCreatePromoCodeInput,
    UpdatePromoCodeInput as TktUpdatePromoCodeInput,
    CheckInTicketInput,
    TransferTicketInput,
    CancelTicketInput,
)
from . import payment_mutations
from . import ticket_mutations
from .waitlist_types import (
    WaitlistJoinResponseType,
    WaitlistLeaveResponseType,
    WaitlistAcceptOfferResponseType,
    BulkSendOffersResponseType,
    UpdateCapacityResponseType,
    WaitlistEntryType,
    JoinWaitlistInput,
    LeaveWaitlistInput,
    AcceptOfferInput,
    DeclineOfferInput,
    RemoveFromWaitlistInput,
    SendOfferInput,
    BulkSendOffersInput,
    UpdateCapacityInput,
)
from .waitlist_mutations import WaitlistMutations


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
    sessionDate: Optional[str] = None  # YYYY-MM-DD (optional convenience)
    startTime: str  # ISO datetime string (e.g., "2024-03-15T09:00:00")
    endTime: str    # ISO datetime string (e.g., "2024-03-15T10:00:00")
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
    sessionDate: Optional[str] = None  # YYYY-MM-DD (optional convenience)
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
    def unpublishEvent(self, id: str, info: Info) -> EventType:
        """
        Revert a published event back to draft (removes from public discovery).
        """
        user = info.context.user
        if not user or not user.get("sub"):
            raise HTTPException(status_code=403, detail="Not authorized")

        db = info.context.db
        user_id = user["sub"]
        user_role = user.get("role")

        event_to_unpublish = crud.event.get(db, id=id)
        if not event_to_unpublish:
            raise HTTPException(status_code=404, detail="Event not found")

        if event_to_unpublish.owner_id != user_id and user_role not in ["OWNER", "ADMIN"]:
            raise HTTPException(
                status_code=403, detail="Not authorized to unpublish this event"
            )

        if event_to_unpublish.is_archived:
            raise HTTPException(
                status_code=409, detail="Cannot unpublish an archived event"
            )

        if event_to_unpublish.status == "draft":
            raise HTTPException(
                status_code=409, detail="Event is already in draft status"
            )

        return crud.event.unpublish(db, db_obj=event_to_unpublish, user_id=user_id)

    @strawberry.mutation
    def createSession(self, sessionIn: SessionCreateInput, info: Info) -> SessionType:
        if not info.context.user or not info.context.user.get("orgId"):
            raise HTTPException(status_code=403, detail="Not authorized")
        db = info.context.db
        producer = info.context.producer
        # Helper to accept either full ISO timestamps or split date + time values
        def parse_datetime(date_str: Optional[str], time_str: str, field_name: str) -> datetime:
            # If the client already sent a full ISO string, try parsing directly.
            candidate = time_str.replace("Z", "+00:00")
            try:
                if "T" in candidate:
                    return datetime.fromisoformat(candidate)
            except ValueError:
                pass

            # Fall back to combining a supplied sessionDate with a time like "10:40" or "10:40:00"
            if not date_str:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid {field_name}. Provide ISO datetime or include sessionDate + time.",
                )
            normalized_time = time_str
            if len(normalized_time.split(":")) == 2:
                normalized_time = f"{normalized_time}:00"
            combined = f"{date_str}T{normalized_time}"
            try:
                return datetime.fromisoformat(combined)
            except ValueError:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid {field_name}. Use ISO datetime or sessionDate (YYYY-MM-DD) with HH:MM.",
                )

        full_start_datetime = parse_datetime(sessionIn.sessionDate, sessionIn.startTime, "startTime")
        full_end_datetime = parse_datetime(sessionIn.sessionDate, sessionIn.endTime, "endTime")
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
            session_date = update_data.get("sessionDate")
            start_time_raw = update_data.pop("startTime")
            try:
                update_data["start_time"] = datetime.fromisoformat(
                    start_time_raw.replace("Z", "+00:00")
                ) if "T" in start_time_raw else datetime.fromisoformat(
                    f"{session_date}T{start_time_raw if len(start_time_raw.split(':')) != 2 else start_time_raw + ':00'}"
                )
            except Exception:
                raise HTTPException(
                    status_code=400,
                    detail="Invalid startTime. Use ISO datetime or sessionDate (YYYY-MM-DD) with HH:MM.",
                )
        if "endTime" in update_data:
            session_date = update_data.get("sessionDate")
            end_time_raw = update_data.pop("endTime")
            try:
                update_data["end_time"] = datetime.fromisoformat(
                    end_time_raw.replace("Z", "+00:00")
                ) if "T" in end_time_raw else datetime.fromisoformat(
                    f"{session_date}T{end_time_raw if len(end_time_raw.split(':')) != 2 else end_time_raw + ':00'}"
                )
            except Exception:
                raise HTTPException(
                    status_code=400,
                    detail="Invalid endTime. Use ISO datetime or sessionDate (YYYY-MM-DD) with HH:MM.",
                )
        # Remove helper-only field to avoid schema validation issues
        update_data.pop("sessionDate", None)
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

    # --- PAYMENT MUTATIONS ---

    @strawberry.mutation
    async def createCheckoutSession(
        self, input: CreateOrderInput, info: Info
    ) -> CheckoutSessionType:
        """
        Create a checkout session with order and payment intent.
        Returns checkout session with client secret for Stripe Elements.
        """
        return await payment_mutations.create_checkout_session(input, info)

    @strawberry.mutation
    async def cancelOrder(self, orderId: strawberry.ID, info: Info) -> OrderType:
        """
        Cancel a pending order (before payment).
        """
        return await payment_mutations.cancel_order(str(orderId), info)

    @strawberry.mutation
    async def applyPromoCode(
        self, orderId: strawberry.ID, promoCode: str, info: Info
    ) -> OrderType:
        """
        Apply promo code to a pending order.
        """
        return await payment_mutations.apply_promo_code(str(orderId), promoCode, info)

    @strawberry.mutation
    async def removePromoCode(self, orderId: strawberry.ID, info: Info) -> OrderType:
        """
        Remove promo code from a pending order.
        """
        return await payment_mutations.remove_promo_code(str(orderId), info)

    @strawberry.mutation
    async def initiateRefund(self, input: InitiateRefundInput, info: Info) -> RefundType:
        """
        Initiate a refund for a completed order (organizer only).
        """
        return await payment_mutations.initiate_refund(input, info)

    @strawberry.mutation
    async def cancelRefund(self, refundId: str, info: Info) -> RefundType:
        """
        Cancel a pending refund (organizer only).
        """
        return await payment_mutations.cancel_refund(refundId, info)

    @strawberry.mutation
    def createTicketType(
        self, input: TicketTypeCreateInput, info: Info
    ) -> TicketTypeType:
        """
        Create a new ticket type for an event (organizer only).
        """
        return payment_mutations.create_ticket_type(input, info)

    @strawberry.mutation
    def updateTicketType(
        self, id: strawberry.ID, input: TicketTypeUpdateInput, info: Info
    ) -> TicketTypeType:
        """
        Update a ticket type (organizer only).
        """
        return payment_mutations.update_ticket_type(str(id), input, info)

    @strawberry.mutation
    def archiveTicketType(self, id: strawberry.ID, info: Info) -> TicketTypeType:
        """
        Archive a ticket type (organizer only).
        """
        return payment_mutations.archive_ticket_type(str(id), info)

    @strawberry.mutation
    async def deleteTicketType(self, id: strawberry.ID, info: Info) -> bool:
        """
        Delete a ticket type (organizer only, only if no sales).
        """
        tm = ticket_mutations.TicketManagementMutations()
        return await tm.deleteTicketType(info, str(id))

    @strawberry.mutation
    def createPromoCode(
        self, input: PromoCodeCreateInput, info: Info
    ) -> PromoCodeType:
        """
        Create a new promo code (organizer only).
        """
        return payment_mutations.create_promo_code(input, info)

    @strawberry.mutation
    def archivePromoCode(self, promoCodeId: str, info: Info) -> PromoCodeType:
        """
        Deactivate a promo code (organizer only).
        """
        return payment_mutations.archive_promo_code(promoCodeId, info)

    # --- TICKET MANAGEMENT MUTATIONS ---

    @strawberry.mutation
    async def createTicketTypeAdmin(
        self, input: TktCreateTicketTypeInput, organizationId: str, info: Info
    ) -> TicketTypeFullType:
        """Create a new ticket type with full features."""
        tm = ticket_mutations.TicketManagementMutations()
        return await tm.createTicketType(info, input, organizationId)

    @strawberry.mutation
    async def updateTicketTypeAdmin(
        self, id: strawberry.ID, input: TktUpdateTicketTypeInput, info: Info
    ) -> Optional[TicketTypeFullType]:
        """Update a ticket type with full features."""
        tm = ticket_mutations.TicketManagementMutations()
        return await tm.updateTicketType(info, str(id), input)

    @strawberry.mutation
    async def deleteTicketTypeAdmin(self, id: strawberry.ID, info: Info) -> bool:
        """Delete a ticket type (only if no sales)."""
        tm = ticket_mutations.TicketManagementMutations()
        return await tm.deleteTicketType(info, str(id))

    @strawberry.mutation
    async def reorderTicketTypes(
        self, input: ReorderTicketTypesInput, info: Info
    ) -> List[TicketTypeFullType]:
        """Reorder ticket types for an event."""
        tm = ticket_mutations.TicketManagementMutations()
        return await tm.reorderTicketTypes(info, input)

    @strawberry.mutation
    async def duplicateTicketType(
        self, id: strawberry.ID, info: Info
    ) -> Optional[TicketTypeFullType]:
        """Duplicate a ticket type."""
        tm = ticket_mutations.TicketManagementMutations()
        return await tm.duplicateTicketType(info, str(id))

    @strawberry.mutation
    async def createPromoCodeAdmin(
        self, input: TktCreatePromoCodeInput, organizationId: str, info: Info
    ) -> PromoCodeFullType:
        """Create a new promo code with full features."""
        tm = ticket_mutations.TicketManagementMutations()
        return await tm.createPromoCode(info, input, organizationId)

    @strawberry.mutation
    def updatePromoCode(
        self, id: str, input: TktUpdatePromoCodeInput, info: Info
    ) -> Optional[PromoCodeFullType]:
        """
        Update a promo code (organizer).
        """
        tm = ticket_mutations.TicketManagementMutations()
        return tm.updatePromoCode(info, id, input)

    @strawberry.mutation
    async def updatePromoCodeAdmin(
        self, id: str, input: TktUpdatePromoCodeInput, info: Info
    ) -> Optional[PromoCodeFullType]:
        """Update a promo code."""
        tm = ticket_mutations.TicketManagementMutations()
        return await tm.updatePromoCode(info, id, input)

    @strawberry.mutation
    async def deletePromoCode(self, id: str, info: Info) -> bool:
        """Delete a promo code."""
        tm = ticket_mutations.TicketManagementMutations()
        return await tm.deletePromoCode(info, id)

    @strawberry.mutation
    async def deletePromoCodeAdmin(self, id: str, info: Info) -> bool:
        """Delete a promo code."""
        tm = ticket_mutations.TicketManagementMutations()
        return await tm.deletePromoCode(info, id)

    @strawberry.mutation
    async def deactivatePromoCodeAdmin(
        self, id: str, info: Info
    ) -> Optional[PromoCodeFullType]:
        """Deactivate a promo code (soft disable)."""
        tm = ticket_mutations.TicketManagementMutations()
        return await tm.deactivatePromoCode(info, id)

    @strawberry.mutation
    async def checkInTicket(
        self, input: CheckInTicketInput, info: Info
    ) -> TicketGQLType:
        """Check in a ticket by code."""
        tm = ticket_mutations.TicketManagementMutations()
        return await tm.checkInTicket(info, input)

    @strawberry.mutation
    async def reverseCheckIn(self, ticketId: str, info: Info) -> TicketGQLType:
        """Reverse a check-in (undo)."""
        tm = ticket_mutations.TicketManagementMutations()
        return await tm.reverseCheckIn(info, ticketId)

    @strawberry.mutation
    async def cancelTicket(
        self, input: CancelTicketInput, info: Info
    ) -> TicketGQLType:
        """Cancel a ticket."""
        tm = ticket_mutations.TicketManagementMutations()
        return await tm.cancelTicket(info, input)

    @strawberry.mutation
    async def resendTicketEmail(self, ticketId: str, info: Info) -> bool:
        """Resend ticket confirmation email."""
        tm = ticket_mutations.TicketManagementMutations()
        return await tm.resendTicketEmail(info, ticketId)

    @strawberry.mutation
    async def transferTicket(
        self, input: TransferTicketInput, info: Info
    ) -> TicketGQLType:
        """Transfer a ticket to a new attendee."""
        tm = ticket_mutations.TicketManagementMutations()
        return await tm.transferTicket(info, input)

    # --- WAITLIST MUTATIONS ---

    @strawberry.mutation
    def join_waitlist(
        self, input: JoinWaitlistInput, info: Info
    ) -> WaitlistJoinResponseType:
        """Join session waitlist."""
        wm = WaitlistMutations()
        return wm.join_waitlist(input, info)

    @strawberry.mutation
    def leave_waitlist(
        self, input: LeaveWaitlistInput, info: Info
    ) -> WaitlistLeaveResponseType:
        """Leave session waitlist."""
        wm = WaitlistMutations()
        return wm.leave_waitlist(input, info)

    @strawberry.mutation
    def accept_waitlist_offer(
        self, input: AcceptOfferInput, info: Info
    ) -> WaitlistAcceptOfferResponseType:
        """Accept waitlist offer using JWT token."""
        wm = WaitlistMutations()
        return wm.accept_waitlist_offer(input, info)

    @strawberry.mutation
    def decline_waitlist_offer(
        self, input: DeclineOfferInput, info: Info
    ) -> WaitlistLeaveResponseType:
        """Decline waitlist offer."""
        wm = WaitlistMutations()
        return wm.decline_waitlist_offer(input, info)

    @strawberry.mutation
    def remove_from_waitlist(
        self, input: RemoveFromWaitlistInput, info: Info
    ) -> WaitlistLeaveResponseType:
        """[ADMIN] Remove a user from waitlist."""
        wm = WaitlistMutations()
        return wm.remove_from_waitlist(input, info)

    @strawberry.mutation
    def send_waitlist_offer(
        self, input: SendOfferInput, info: Info
    ) -> WaitlistEntryType:
        """[ADMIN] Manually send offer to a specific user."""
        wm = WaitlistMutations()
        return wm.send_waitlist_offer(input, info)

    @strawberry.mutation
    def bulk_send_waitlist_offers(
        self, input: BulkSendOffersInput, info: Info
    ) -> BulkSendOffersResponseType:
        """[ADMIN] Bulk send offers to multiple users."""
        wm = WaitlistMutations()
        return wm.bulk_send_waitlist_offers(input, info)

    @strawberry.mutation
    def update_session_capacity(
        self, input: UpdateCapacityInput, info: Info
    ) -> UpdateCapacityResponseType:
        """[ADMIN] Update session maximum capacity."""
        wm = WaitlistMutations()
        return wm.update_session_capacity(input, info)