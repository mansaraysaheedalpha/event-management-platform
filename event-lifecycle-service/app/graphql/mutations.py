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
from .types import EventType, SessionType, RegistrationType, SpeakerType, VenueType, AdType, OfferType
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
from .ad_mutations import (
    AdMutations,
    AdCreateInput,
    AdUpdateInput,
    AdImpressionInput,
    AdTrackingResult,
    AdClickResult,
)
from .offer_mutations import (
    OfferMutations,
    OfferCreateInput,
    OfferUpdateInput,
    OfferPurchaseResponse,
)
from .sponsor_mutations import SponsorMutations
from .sponsor_types import (
    SponsorTierType,
    SponsorTierCreateInput,
    SponsorTierUpdateInput,
    SponsorType,
    SponsorCreateInput,
    SponsorUpdateInput,
    SponsorInvitationType,
    SponsorInvitationCreateInput,
    SponsorInvitationAcceptResponse,
    SponsorUserType,
    SponsorLeadType,
    SponsorLeadUpdateInput,
)
from .types import (
    VirtualAttendanceType,
    JoinVirtualSessionResponse,
    LeaveVirtualSessionResponse,
)


# ==== VIRTUAL EVENT ENUMS FOR INPUT (Phase 1) ====
from enum import Enum as PyEnum


@strawberry.enum
class EventTypeInput(PyEnum):
    """Event type classification for virtual event support."""
    IN_PERSON = "IN_PERSON"
    VIRTUAL = "VIRTUAL"
    HYBRID = "HYBRID"


@strawberry.enum
class SessionTypeInput(PyEnum):
    """Session type classification for virtual event support."""
    MAINSTAGE = "MAINSTAGE"
    BREAKOUT = "BREAKOUT"
    WORKSHOP = "WORKSHOP"
    NETWORKING = "NETWORKING"
    EXPO = "EXPO"


@strawberry.input
class VirtualSettingsInput:
    """Virtual event configuration settings input."""
    streamingProvider: Optional[str] = None
    streamingUrl: Optional[str] = None
    recordingEnabled: Optional[bool] = True
    autoCaptions: Optional[bool] = False
    timezoneDisplay: Optional[str] = None
    lobbyEnabled: Optional[bool] = False
    lobbyVideoUrl: Optional[str] = None
    maxConcurrentViewers: Optional[int] = None
    geoRestrictions: Optional[List[str]] = None


# --- All Input types defined at the top ---
@strawberry.input
class EventCreateInput:
    name: str
    description: Optional[str]
    startDate: str
    endDate: str
    venueId: Optional[str] = None
    imageUrl: Optional[str] = None
    # Virtual Event Support (Phase 1)
    eventType: Optional[EventTypeInput] = EventTypeInput.IN_PERSON
    virtualSettings: Optional[VirtualSettingsInput] = None


@strawberry.input
class EventUpdateInput:
    name: Optional[str] = None
    description: Optional[str] = None
    startDate: Optional[str] = None
    endDate: Optional[str] = None
    venueId: Optional[str] = None
    isPublic: Optional[bool] = None
    imageUrl: Optional[str] = None
    # Virtual Event Support (Phase 1)
    eventType: Optional[EventTypeInput] = None
    virtualSettings: Optional[VirtualSettingsInput] = None


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
    breakoutEnabled: Optional[bool] = False  # Defaults to disabled
    # Virtual Session Support (Phase 1)
    sessionType: Optional[SessionTypeInput] = SessionTypeInput.MAINSTAGE
    streamingProvider: Optional[str] = None
    virtualRoomId: Optional[str] = None
    streamingUrl: Optional[str] = None
    isRecordable: Optional[bool] = True
    requiresCamera: Optional[bool] = False
    requiresMicrophone: Optional[bool] = False
    maxParticipants: Optional[int] = None
    broadcastOnly: Optional[bool] = True
    # Green Room / Backstage Support (P1)
    greenRoomEnabled: Optional[bool] = True
    greenRoomOpensMinutesBefore: Optional[int] = 15
    greenRoomNotes: Optional[str] = None


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
    userId: Optional[str] = None  # Links speaker to a platform user account


@strawberry.input
class SpeakerUpdateInput:
    name: Optional[str] = None
    bio: Optional[str] = None
    expertise: Optional[List[str]] = None
    userId: Optional[str] = None  # Links speaker to a platform user account


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
    breakoutEnabled: Optional[bool] = None
    # Virtual Session Support (Phase 1)
    sessionType: Optional[SessionTypeInput] = None
    streamingProvider: Optional[str] = None
    virtualRoomId: Optional[str] = None
    streamingUrl: Optional[str] = None
    recordingUrl: Optional[str] = None
    isRecordable: Optional[bool] = None
    requiresCamera: Optional[bool] = None
    requiresMicrophone: Optional[bool] = None
    maxParticipants: Optional[int] = None
    broadcastOnly: Optional[bool] = None
    # Green Room / Backstage Support (P1)
    greenRoomEnabled: Optional[bool] = None
    greenRoomOpensMinutesBefore: Optional[int] = None
    greenRoomNotes: Optional[str] = None


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

        # Convert virtual_settings input to dict
        virtual_settings_dict = None
        if eventIn.virtualSettings:
            virtual_settings_dict = {
                "streaming_provider": eventIn.virtualSettings.streamingProvider,
                "streaming_url": eventIn.virtualSettings.streamingUrl,
                "recording_enabled": eventIn.virtualSettings.recordingEnabled,
                "auto_captions": eventIn.virtualSettings.autoCaptions,
                "timezone_display": eventIn.virtualSettings.timezoneDisplay,
                "lobby_enabled": eventIn.virtualSettings.lobbyEnabled,
                "lobby_video_url": eventIn.virtualSettings.lobbyVideoUrl,
                "max_concurrent_viewers": eventIn.virtualSettings.maxConcurrentViewers,
                "geo_restrictions": eventIn.virtualSettings.geoRestrictions,
            }

        event_schema = EventCreate(
            owner_id=user_id,
            name=eventIn.name,
            description=eventIn.description,
            start_date=eventIn.startDate,
            end_date=eventIn.endDate,
            venue_id=eventIn.venueId,
            imageUrl=eventIn.imageUrl,
            event_type=eventIn.eventType.value if eventIn.eventType else "IN_PERSON",
            virtual_settings=virtual_settings_dict,
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

        # Handle virtual event fields (Phase 1)
        if "eventType" in update_data:
            event_type_input = update_data.pop("eventType")
            update_data["event_type"] = event_type_input.value if event_type_input else None
        if "virtualSettings" in update_data:
            vs = update_data.pop("virtualSettings")
            if vs:
                update_data["virtual_settings"] = {
                    "streaming_provider": vs.streamingProvider,
                    "streaming_url": vs.streamingUrl,
                    "recording_enabled": vs.recordingEnabled,
                    "auto_captions": vs.autoCaptions,
                    "timezone_display": vs.timezoneDisplay,
                    "lobby_enabled": vs.lobbyEnabled,
                    "lobby_video_url": vs.lobbyVideoUrl,
                    "max_concurrent_viewers": vs.maxConcurrentViewers,
                    "geo_restrictions": vs.geoRestrictions,
                }

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
            breakout_enabled=sessionIn.breakoutEnabled if sessionIn.breakoutEnabled is not None else False,
            # Virtual Session Support (Phase 1)
            session_type=sessionIn.sessionType.value if sessionIn.sessionType else "MAINSTAGE",
            streaming_provider=sessionIn.streamingProvider,
            virtual_room_id=sessionIn.virtualRoomId,
            streaming_url=sessionIn.streamingUrl,
            is_recordable=sessionIn.isRecordable if sessionIn.isRecordable is not None else True,
            requires_camera=sessionIn.requiresCamera if sessionIn.requiresCamera is not None else False,
            requires_microphone=sessionIn.requiresMicrophone if sessionIn.requiresMicrophone is not None else False,
            max_participants=sessionIn.maxParticipants,
            broadcast_only=sessionIn.broadcastOnly if sessionIn.broadcastOnly is not None else True,
            # Green Room / Backstage Support (P1)
            green_room_enabled=sessionIn.greenRoomEnabled if sessionIn.greenRoomEnabled is not None else True,
            green_room_opens_minutes_before=sessionIn.greenRoomOpensMinutesBefore if sessionIn.greenRoomOpensMinutesBefore is not None else 15,
            green_room_notes=sessionIn.greenRoomNotes,
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
        if "breakoutEnabled" in update_data:
            update_data["breakout_enabled"] = update_data.pop("breakoutEnabled")

        # Handle virtual session fields (Phase 1)
        if "sessionType" in update_data:
            session_type_input = update_data.pop("sessionType")
            update_data["session_type"] = session_type_input.value if session_type_input else None
        if "streamingProvider" in update_data:
            update_data["streaming_provider"] = update_data.pop("streamingProvider")
        if "virtualRoomId" in update_data:
            update_data["virtual_room_id"] = update_data.pop("virtualRoomId")
        if "streamingUrl" in update_data:
            update_data["streaming_url"] = update_data.pop("streamingUrl")
        if "recordingUrl" in update_data:
            update_data["recording_url"] = update_data.pop("recordingUrl")
        if "isRecordable" in update_data:
            update_data["is_recordable"] = update_data.pop("isRecordable")
        if "requiresCamera" in update_data:
            update_data["requires_camera"] = update_data.pop("requiresCamera")
        if "requiresMicrophone" in update_data:
            update_data["requires_microphone"] = update_data.pop("requiresMicrophone")
        if "maxParticipants" in update_data:
            update_data["max_participants"] = update_data.pop("maxParticipants")
        if "broadcastOnly" in update_data:
            update_data["broadcast_only"] = update_data.pop("broadcastOnly")

        # Handle Green Room fields (P1)
        if "greenRoomEnabled" in update_data:
            update_data["green_room_enabled"] = update_data.pop("greenRoomEnabled")
        if "greenRoomOpensMinutesBefore" in update_data:
            update_data["green_room_opens_minutes_before"] = update_data.pop("greenRoomOpensMinutesBefore")
        if "greenRoomNotes" in update_data:
            update_data["green_room_notes"] = update_data.pop("greenRoomNotes")

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
            name=speakerIn.name,
            bio=speakerIn.bio,
            expertise=speakerIn.expertise,
            user_id=speakerIn.userId,  # Link to platform user account
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
        # Convert camelCase GraphQL input to snake_case for schema
        update_data = {}
        for k, v in speakerIn.__dict__.items():
            if v is not None:
                # Convert userId to user_id for the schema
                key = "user_id" if k == "userId" else k
                update_data[key] = v
        update_schema = SpeakerUpdate(**update_data)
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

        # Send registration confirmation email
        # Determine recipient email and name
        if is_guest_reg:
            recipient_email = registrationIn.email
            recipient_name = f"{registrationIn.firstName} {registrationIn.lastName}"
        else:
            recipient_email = user.get("email") if user else None
            first_name = user.get("firstName", "") if user else ""
            last_name = user.get("lastName", "") if user else ""
            recipient_name = f"{first_name} {last_name}".strip() or "Attendee"

        kafka_sent = False
        producer = info.context.producer
        if producer and recipient_email:
            try:
                future = producer.send(
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
                record_metadata = future.get(timeout=10)
                kafka_sent = True
                print(f"[KAFKA] Published registration event for ticket: {registration.ticket_code}, email: {recipient_email}, partition: {record_metadata.partition}, offset: {record_metadata.offset}")
            except Exception as e:
                print(f"[KAFKA ERROR] Failed to publish registration event: {e}")

        # Direct email fallback if Kafka unavailable or failed
        if not kafka_sent and recipient_email:
            try:
                from app.core.email import send_registration_confirmation
                formatted_date = event.start_date.strftime("%B %d, %Y at %I:%M %p")
                result = send_registration_confirmation(
                    to_email=recipient_email,
                    recipient_name=recipient_name,
                    event_name=event.name,
                    event_date=formatted_date,
                    ticket_code=registration.ticket_code,
                    event_location=event.venue.name if event.venue else None,
                )
                if result.get("success"):
                    print(f"[EMAIL DIRECT] Registration confirmation sent to {recipient_email}")
                else:
                    print(f"[EMAIL DIRECT ERROR] Failed: {result.get('error')}")
            except Exception as e:
                print(f"[EMAIL DIRECT ERROR] Failed to send registration email: {e}")

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

    # --- AD MUTATIONS ---

    @strawberry.mutation
    def createAd(self, adIn: AdCreateInput, info: Info) -> AdType:
        """
        Create a new advertisement for an event.
        Requires authentication and organizer access.
        """
        am = AdMutations()
        return am.create_ad(adIn, info)

    @strawberry.mutation
    def updateAd(self, id: str, adIn: AdUpdateInput, info: Info) -> AdType:
        """
        Update an existing advertisement.
        Requires authentication and organizer access.
        """
        am = AdMutations()
        return am.update_ad(id, adIn, info)

    @strawberry.mutation
    def deleteAd(self, id: str, info: Info) -> bool:
        """
        Delete (archive) an advertisement.
        Requires authentication and organizer access.
        """
        am = AdMutations()
        return am.delete_ad(id, info)

    @strawberry.mutation
    def trackAdImpressions(
        self, impressions: List[AdImpressionInput], info: Info
    ) -> AdTrackingResult:
        """
        Track multiple ad impressions in bulk.
        Public endpoint - authentication optional.
        """
        am = AdMutations()
        return am.track_ad_impressions(impressions, info)

    @strawberry.mutation
    def trackAdClick(
        self, adId: str, sessionContext: Optional[str] = None, info: Info = None
    ) -> AdClickResult:
        """
        Track an ad click and return the redirect URL.
        Public endpoint - authentication optional.
        """
        am = AdMutations()
        return am.track_ad_click(adId, sessionContext, info)

    # --- OFFER MUTATIONS ---

    @strawberry.mutation
    def createOffer(self, offerIn: OfferCreateInput, info: Info) -> OfferType:
        """
        Create a new offer for an event.
        Requires authentication and organizer access.
        """
        om = OfferMutations()
        return om.create_offer(offerIn, info)

    @strawberry.mutation
    def updateOffer(self, id: str, offerIn: OfferUpdateInput, info: Info) -> OfferType:
        """
        Update an existing offer.
        Requires authentication and organizer access.
        """
        om = OfferMutations()
        return om.update_offer(id, offerIn, info)

    @strawberry.mutation
    def deleteOffer(self, id: str, info: Info) -> bool:
        """
        Delete (archive) an offer.
        Requires authentication and organizer access.
        """
        om = OfferMutations()
        return om.delete_offer(id, info)

    @strawberry.mutation
    async def purchaseOffer(
        self, offerId: str, quantity: int, info: Info
    ) -> OfferPurchaseResponse:
        """
        Purchase an offer - creates a Stripe checkout session.
        Requires authentication.
        """
        om = OfferMutations()
        return await om.purchase_offer(offerId, quantity, info)

    # --- SPONSOR MUTATIONS ---

    @strawberry.mutation
    def createSponsorTier(
        self, eventId: str, input: SponsorTierCreateInput, info: Info
    ) -> SponsorTierType:
        """Create a new sponsor tier for an event."""
        sm = SponsorMutations()
        return sm.create_sponsor_tier(eventId, input, info)

    @strawberry.mutation
    def updateSponsorTier(
        self, tierId: str, input: SponsorTierUpdateInput, info: Info
    ) -> SponsorTierType:
        """Update a sponsor tier."""
        sm = SponsorMutations()
        return sm.update_sponsor_tier(tierId, input, info)

    @strawberry.mutation
    def deleteSponsorTier(self, tierId: str, info: Info) -> bool:
        """Delete a sponsor tier."""
        sm = SponsorMutations()
        return sm.delete_sponsor_tier(tierId, info)

    @strawberry.mutation
    def createSponsor(
        self, eventId: str, input: SponsorCreateInput, info: Info
    ) -> SponsorType:
        """Create a new sponsor for an event."""
        sm = SponsorMutations()
        return sm.create_sponsor(eventId, input, info)

    @strawberry.mutation
    def updateSponsor(
        self, sponsorId: str, input: SponsorUpdateInput, info: Info
    ) -> SponsorType:
        """Update a sponsor."""
        sm = SponsorMutations()
        return sm.update_sponsor(sponsorId, input, info)

    @strawberry.mutation
    def archiveSponsor(self, sponsorId: str, info: Info) -> SponsorType:
        """Archive a sponsor."""
        sm = SponsorMutations()
        return sm.archive_sponsor(sponsorId, info)

    @strawberry.mutation
    def restoreSponsor(self, sponsorId: str, info: Info) -> SponsorType:
        """Restore an archived sponsor."""
        sm = SponsorMutations()
        return sm.restore_sponsor(sponsorId, info)

    @strawberry.mutation
    def createSponsorInvitation(
        self, sponsorId: str, input: SponsorInvitationCreateInput, info: Info
    ) -> SponsorInvitationType:
        """Create and send an invitation to join a sponsor team."""
        sm = SponsorMutations()
        return sm.create_sponsor_invitation(sponsorId, input, info)

    @strawberry.mutation
    def resendSponsorInvitation(
        self, invitationId: str, info: Info
    ) -> SponsorInvitationType:
        """Resend a pending invitation."""
        sm = SponsorMutations()
        return sm.resend_sponsor_invitation(invitationId, info)

    @strawberry.mutation
    def revokeSponsorInvitation(self, invitationId: str, info: Info) -> bool:
        """Revoke a pending invitation."""
        sm = SponsorMutations()
        return sm.revoke_sponsor_invitation(invitationId, info)

    @strawberry.mutation
    def acceptSponsorInvitation(
        self, token: str, info: Info
    ) -> SponsorInvitationAcceptResponse:
        """Accept a sponsor invitation using the token."""
        sm = SponsorMutations()
        return sm.accept_sponsor_invitation(token, info)

    @strawberry.mutation
    def updateSponsorUser(
        self,
        sponsorUserId: str,
        info: Info,
        role: Optional[str] = None,
        canViewLeads: Optional[bool] = None,
        canExportLeads: Optional[bool] = None,
        canMessageAttendees: Optional[bool] = None,
        canManageBooth: Optional[bool] = None,
        canInviteOthers: Optional[bool] = None,
        isActive: Optional[bool] = None,
    ) -> SponsorUserType:
        """Update a sponsor user's permissions."""
        sm = SponsorMutations()
        return sm.update_sponsor_user(
            sponsorUserId,
            role=role,
            can_view_leads=canViewLeads,
            can_export_leads=canExportLeads,
            can_message_attendees=canMessageAttendees,
            can_manage_booth=canManageBooth,
            can_invite_others=canInviteOthers,
            is_active=isActive,
            info=info
        )

    @strawberry.mutation
    def removeSponsorUser(self, sponsorUserId: str, info: Info) -> bool:
        """Remove a user from a sponsor team."""
        sm = SponsorMutations()
        return sm.remove_sponsor_user(sponsorUserId, info)

    @strawberry.mutation
    def updateSponsorLead(
        self, leadId: str, input: SponsorLeadUpdateInput, info: Info
    ) -> SponsorLeadType:
        """Update a sponsor lead."""
        sm = SponsorMutations()
        return sm.update_sponsor_lead(leadId, input, info)

    @strawberry.mutation
    def starSponsorLead(
        self, leadId: str, starred: bool, info: Info
    ) -> SponsorLeadType:
        """Star or unstar a lead."""
        sm = SponsorMutations()
        return sm.star_sponsor_lead(leadId, starred, info)

    @strawberry.mutation
    def archiveSponsorLead(self, leadId: str, info: Info) -> SponsorLeadType:
        """Archive a lead."""
        sm = SponsorMutations()
        return sm.archive_sponsor_lead(leadId, info)

    # --- VIRTUAL ATTENDANCE MUTATIONS ---

    @strawberry.mutation
    def joinVirtualSession(
        self,
        sessionId: str,
        info: Info,
        deviceType: Optional[str] = None,
        userAgent: Optional[str] = None,
    ) -> JoinVirtualSessionResponse:
        """
        Record that the current user has joined a virtual session.
        Creates a new attendance record with the join timestamp.
        """
        user = info.context.user
        if not user or not user.get("sub"):
            raise HTTPException(status_code=401, detail="Authentication required")

        db = info.context.db
        user_id = user["sub"]

        # Get the session to find the event_id
        session = crud.session.get(db, id=sessionId)
        if not session:
            return JoinVirtualSessionResponse(
                success=False,
                attendance=None,
                message="Session not found"
            )

        # Verify user is registered for the event
        registration = crud.registration.get_by_user_or_email(
            db, event_id=session.event_id, user_id=user_id
        )
        if not registration:
            return JoinVirtualSessionResponse(
                success=False,
                attendance=None,
                message="You must be registered for this event to join"
            )

        # Check for existing active attendance (no left_at)
        existing = crud.virtual_attendance.get_active_attendance(
            db, user_id=user_id, session_id=sessionId
        )
        if existing:
            # User already has an active session - return it
            return JoinVirtualSessionResponse(
                success=True,
                attendance=VirtualAttendanceType(
                    id=existing.id,
                    userId=existing.user_id,
                    sessionId=existing.session_id,
                    eventId=existing.event_id,
                    joinedAt=existing.joined_at,
                    leftAt=existing.left_at,
                    watchDurationSeconds=existing.watch_duration_seconds,
                    deviceType=existing.device_type,
                ),
                message="Already joined"
            )

        # Create new attendance record
        attendance = crud.virtual_attendance.join_session(
            db,
            user_id=user_id,
            session_id=sessionId,
            event_id=session.event_id,
            device_type=deviceType,
            user_agent=userAgent,
        )

        return JoinVirtualSessionResponse(
            success=True,
            attendance=VirtualAttendanceType(
                id=attendance.id,
                userId=attendance.user_id,
                sessionId=attendance.session_id,
                eventId=attendance.event_id,
                joinedAt=attendance.joined_at,
                leftAt=attendance.left_at,
                watchDurationSeconds=attendance.watch_duration_seconds,
                deviceType=attendance.device_type,
            ),
            message="Joined successfully"
        )

    @strawberry.mutation
    def leaveVirtualSession(
        self,
        sessionId: str,
        info: Info,
    ) -> LeaveVirtualSessionResponse:
        """
        Record that the current user has left a virtual session.
        Updates the attendance record with leave timestamp and duration.
        """
        user = info.context.user
        if not user or not user.get("sub"):
            raise HTTPException(status_code=401, detail="Authentication required")

        db = info.context.db
        user_id = user["sub"]

        # Leave the session (updates left_at and calculates duration)
        attendance = crud.virtual_attendance.leave_session(
            db, user_id=user_id, session_id=sessionId
        )

        if not attendance:
            return LeaveVirtualSessionResponse(
                success=False,
                attendance=None,
                watchDurationSeconds=None,
                message="No active session found"
            )

        return LeaveVirtualSessionResponse(
            success=True,
            attendance=VirtualAttendanceType(
                id=attendance.id,
                userId=attendance.user_id,
                sessionId=attendance.session_id,
                eventId=attendance.event_id,
                joinedAt=attendance.joined_at,
                leftAt=attendance.left_at,
                watchDurationSeconds=attendance.watch_duration_seconds,
                deviceType=attendance.device_type,
            ),
            watchDurationSeconds=attendance.watch_duration_seconds,
            message="Left successfully"
        )