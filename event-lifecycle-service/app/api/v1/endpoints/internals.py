# app/api/v1/endpoints/internals.py
import json
from app.db.redis import redis_client
from typing import List
from datetime import datetime, timezone, timedelta
from jose import jwt
from app.core.config import settings
from fastapi import APIRouter, Depends, HTTPException, status, Response, Security
from sqlalchemy.orm import Session
from app.crud import crud_ad, crud_offer, crud_waitlist,  crud_session
from app.models.registration import Registration

from app.api import deps
from app.db.session import get_db
from app.crud import crud_ad
from app.schemas.internal import (
    AdContent,
    AgendaUpdateNotification,
    CapacityUpdateNotification,
    OfferContent,
    WaitlistOffer,
    TicketValidationRequest,
    ValidationResult,
)
from app.schemas.waitlist import WaitlistEntry
from app.schemas.session import Session as SessionSchema

router = APIRouter(tags=["Internal"])


@router.get("/internal/ads/{adId}", response_model=AdContent)
def get_ad_content_by_id(
    adId: str,
    db: Session = Depends(get_db),
    api_key: str = Depends(deps.get_internal_api_key),
):
    """
    An internal endpoint for other services to fetch ad content from the database.
    """
    ad = crud_ad.ad.get(db, id=adId)
    if not ad or ad.is_archived:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Ad not found"
        )

    return AdContent(
        id=ad.id,
        event_id=ad.event_id,
        type=ad.content_type,
        media_url=ad.media_url,
        click_url=ad.click_url,
    )


@router.post("/internal/notify/agenda-update", status_code=status.HTTP_202_ACCEPTED)
def notify_agenda_update(
    notification: AgendaUpdateNotification,
    api_key: str = Depends(deps.get_internal_api_key),
):
    """
    Accepts a notification and publishes it to a Redis channel
    for the real-time service to consume.
    """
    # The channel name can be defined by your platform's standards
    channel = "platform.events.agenda.v1"
    message = notification.model_dump_json()
    redis_client.publish(channel, message)
    return {"message": "Notification accepted"}


@router.post("/internal/notify/capacity-update", status_code=status.HTTP_202_ACCEPTED)
def notify_capacity_update(
    notification: CapacityUpdateNotification,
    api_key: str = Depends(deps.get_internal_api_key),
):
    """
    Accepts a capacity update and publishes it to a Redis channel.
    """
    channel = "platform.events.capacity.v1"
    message = notification.model_dump_json()
    redis_client.publish(channel, message)
    return {"message": "Notification accepted"}


@router.get("/internal/offers/{offerId}", response_model=OfferContent)
def get_offer_content_by_id(
    offerId: str,
    db: Session = Depends(get_db),  # Add db session
    api_key: str = Depends(deps.get_internal_api_key),
):
    """
    Fetches offer content by ID from the database.
    """
    offer = crud_offer.offer.get(db, id=offerId)
    if not offer or offer.is_archived:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Offer '{offerId}' not found.",
        )

    # Adapt the database model to the OfferContent schema for the response
    return OfferContent(
        id=offer.id,
        event_id=offer.event_id,
        title=offer.title,
        description=offer.description,
        price=offer.price,
        currency=offer.currency,
    )


@router.get(
    "/internal/sessions/{sessionId}/waitlist-offer", response_model=WaitlistOffer
)
def get_waitlist_offer(
    sessionId: str,
    userId: str,  # The user ID to generate an offer for
    db: Session = Depends(get_db),
    api_key: str = Depends(deps.get_internal_api_key),
):
    """
    Generates a short-lived offer for a user to join a session,
    but only if they are at the top of the waitlist.
    Upon success, the user is removed from the waitlist.
    """
    # --- IMPLEMENTED: Real waitlist logic ---

    # 1. Get the user at the front of the queue for this session.
    first_in_queue = crud_waitlist.waitlist.get_first_in_queue(db, session_id=sessionId)

    # 2. Verify that there is someone on the waitlist and it's the correct user.
    if not first_in_queue or first_in_queue.user_id != userId:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User is not at the top of the waitlist for this session.",
        )

    # 3. Create a special, short-lived JWT (5 minutes) as a "join token".
    expires_delta = timedelta(minutes=5)
    expires_at = datetime.now(timezone.utc) + expires_delta

    token_payload = {
        "sub": userId,
        "session_id": sessionId,
        "scope": "join_session",  # A specific scope for this token
        "exp": expires_at,
    }
    join_token = jwt.encode(token_payload, settings.JWT_SECRET, algorithm="HS256")

    # 4. Atomically remove the user from the waitlist now that the offer is generated.
    crud_waitlist.waitlist.remove(db, id=first_in_queue.id)

    return WaitlistOffer(
        title="Your Spot is Ready!",
        message=f"A spot has opened up for you in session {sessionId}. Click to join now!",
        join_token=join_token,
        expires_at=expires_at,
    )


@router.post("/internal/tickets/validate", response_model=ValidationResult)
def validate_ticket_internal(
    validation_request: TicketValidationRequest,
    db: Session = Depends(get_db),
    api_key: str = Depends(deps.get_internal_api_key),
):
    """
    Validates a ticket code against the registrations table,
    and marks the ticket as 'checked-in' to prevent reuse.
    """
    # Find the registration by its unique ticket code
    registration = (
        db.query(Registration)
        .filter(Registration.ticket_code == validation_request.ticketCode)
        .first()
    )

    # Check 1: Does the registration exist and is it for the correct event?
    if not registration or registration.event_id != validation_request.eventId:
        return ValidationResult(
            isValid=False,
            ticketCode=validation_request.ticketCode,
            validatedAt=datetime.now(timezone.utc),
            errorReason="Ticket not found or invalid for this event.",
        )

    # Check 2: Has this ticket already been checked in?
    if registration.checked_in_at:
        return ValidationResult(
            isValid=False,
            ticketCode=validation_request.ticketCode,
            validatedAt=datetime.now(timezone.utc),
            errorReason=f"Ticket already checked in at {registration.checked_in_at.isoformat()}",
        )

    # If all checks pass, mark the ticket as checked in NOW
    registration.checked_in_at = datetime.now(timezone.utc)
    registration.status = "checked_in"
    db.commit()
    db.refresh(registration)

    return ValidationResult(
        isValid=True,
        ticketCode=validation_request.ticketCode,
        validatedAt=registration.checked_in_at,
    )


@router.get("/internal/sessions/{session_id}/details", response_model=SessionSchema)
def get_session_details(
    session_id: str,
    db: Session = Depends(get_db),
    api_key: str = Security(deps.get_internal_api_key),
):
    """
    An internal endpoint to get full session details by its ID,
    so other services don't need to guess orgId or eventId.
    Returns session with organization_id populated from the event relationship.
    """
    session = crud_session.session.get(db=db, id=session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # Manually construct response to include organization_id from event relationship
    return SessionSchema(
        id=session.id,
        event_id=session.event_id,
        title=session.title,
        start_time=session.start_time,
        end_time=session.end_time,
        chat_enabled=session.chat_enabled,
        qa_enabled=session.qa_enabled,
        polls_enabled=session.polls_enabled,
        chat_open=session.chat_open,
        qa_open=session.qa_open,
        polls_open=session.polls_open,
        speakers=[],  # Speakers not needed for internal calls
        organization_id=session.event.organization_id if session.event else None,
    )


@router.get("/internal/events/{event_id}/registrations/{user_id}")
def check_user_registration(
    event_id: str,
    user_id: str,
    db: Session = Depends(get_db),
    api_key: str = Security(deps.get_internal_api_key),
):
    """
    Internal endpoint to check if a user is registered for an event.
    Used by real-time service to validate chat/Q&A access.
    Returns registration details if found and active, 404 otherwise.
    """
    registration = (
        db.query(Registration)
        .filter(
            Registration.event_id == event_id,
            Registration.user_id == user_id,
            Registration.is_archived == "false",
            Registration.status != "cancelled",
        )
        .first()
    )

    if not registration:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User is not registered for this event",
        )

    return {
        "id": registration.id,
        "event_id": registration.event_id,
        "user_id": registration.user_id,
        "status": registration.status,
        "ticket_code": registration.ticket_code,
    }


@router.get("/internal/sessions/{session_id}/speakers/{user_id}/check")
def check_if_user_is_speaker(
    session_id: str,
    user_id: str,
    db: Session = Depends(get_db),
    api_key: str = Security(deps.get_internal_api_key),
):
    """
    Internal endpoint to check if a user is assigned as a speaker for a session.
    Used by real-time service for backchannel role-based targeting.

    Returns:
        - is_speaker: True if user is a speaker for this session
        - speaker_id: The speaker record ID if found

    Note: Speakers must have their user_id field populated for this to work.
    """
    from app.models.speaker import Speaker
    from app.models.session_speaker import session_speaker_association

    # Query for a speaker with this user_id that is assigned to this session
    speaker = (
        db.query(Speaker)
        .join(
            session_speaker_association,
            Speaker.id == session_speaker_association.c.speaker_id,
        )
        .filter(
            session_speaker_association.c.session_id == session_id,
            Speaker.user_id == user_id,
            Speaker.is_archived == "false",
        )
        .first()
    )

    if not speaker:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User is not a speaker for this session",
        )

    return {
        "is_speaker": True,
        "speaker_id": speaker.id,
    }


@router.post("/users/batch")
def get_users_batch(
    request: dict,
    db: Session = Depends(get_db),
    api_key: str = Depends(deps.get_internal_api_key),
):
    """
    Internal endpoint to fetch multiple users by their IDs.
    Used by real-time service for booth visitor name resolution.
    """
    from app.models.user import User

    user_ids = request.get("user_ids", [])
    if not user_ids:
        return {"users": []}

    users = db.query(User).filter(User.id.in_(user_ids)).all()

    return {
        "users": [
            {
                "id": user.id,
                "email": user.email,
                "first_name": user.first_name,
                "last_name": user.last_name,
            }
            for user in users
        ]
    }
