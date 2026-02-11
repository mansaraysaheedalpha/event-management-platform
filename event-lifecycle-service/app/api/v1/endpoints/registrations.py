#app/api/v1/endpoints/registrations.py
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api import deps
from app.db.session import get_db
from app.crud import crud_event, crud_registration
from app.schemas.registration import Registration, RegistrationCreate
from app.schemas.token import TokenPayload

router = APIRouter(tags=["Registrations"])


@router.post(
    "/organizations/{orgId}/events/{eventId}/registrations",
    response_model=Registration,
    status_code=status.HTTP_201_CREATED,
)
def create_registration(
    orgId: str,
    eventId: str,
    registration_in: RegistrationCreate,
    db: Session = Depends(get_db),
    current_user: TokenPayload = Depends(deps.get_current_user),
):
    """
    Create a registration for an event.

    This endpoint handles registration for both existing users (by `user_id`)
    and new guest users (by `email` and `name`). It prevents duplicate registrations
    for the same event.
    """
    if current_user.org_id != orgId:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized"
        )

    event = crud_event.event.get(db, id=eventId)
    if not event or event.organization_id != orgId:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Event not found"
        )

    # --- IMPLEMENTED: Duplicate registration check ---
    existing_registration = crud_registration.registration.get_by_user_or_email(
        db,
        event_id=eventId,
        user_id=registration_in.user_id,
        email=registration_in.email,
    )
    if existing_registration:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This user or email is already registered for this event.",
        )
    # --- END IMPLEMENTATION ---

    # --- Event capacity check ---
    if event.max_attendees is not None:
        current_count = crud_registration.registration.get_count_by_event(
            db, event_id=eventId
        )
        if current_count >= event.max_attendees:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="This event has reached its maximum capacity.",
            )

    return crud_registration.registration.create_for_event(
        db, obj_in=registration_in, event_id=eventId
    )


@router.get(
    "/organizations/{orgId}/events/{eventId}/registrations",
    response_model=List[Registration],
)
def list_registrations(
    orgId: str,
    eventId: str,
    db: Session = Depends(get_db),
    current_user: TokenPayload = Depends(deps.get_current_user),
):
    """
    Retrieve a list of all registrations for a specific event.
    """
    if current_user.org_id != orgId:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized"
        )

    # --- IMPLEMENTED: Using the proper CRUD function ---
    registrations = crud_registration.registration.get_multi_by_event(
        db=db, event_id=eventId
    )
    return registrations
