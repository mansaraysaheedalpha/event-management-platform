#app/api/v1/endpoints/events.py
import math
from typing import List
from fastapi import APIRouter, Depends, status, HTTPException, Query, Response
from sqlalchemy.orm import Session
from app.schemas.event_sync_bundle import EventSyncBundle

from app.schemas.event import (
    Event as EventSchema,
    EventCreate,
    EventUpdate,
    PaginatedEvent,
)
from app.schemas.token import TokenPayload
from app.schemas.domain_event import DomainEvent as DomainEventSchema
from app.api import deps
from app.db.session import get_db
from app.crud import crud_event, crud_domain_event

router = APIRouter(tags=["Events"])


@router.post(
    "/organizations/{orgId}/events",
    response_model=EventSchema,
    status_code=status.HTTP_201_CREATED,
)
def create_event(
    orgId: str,
    event_in: EventCreate,
    db: Session = Depends(get_db),
    current_user: TokenPayload = Depends(deps.get_current_user),
):
    """Creates a new event for the specified organization."""
    if current_user.org_id != orgId:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized"
        )
    # NEW: Calling the inherited method from CRUDBase
    return crud_event.event.create_with_organization(db, obj_in=event_in, org_id=orgId)


@router.get("/organizations/{orgId}/events", response_model=PaginatedEvent)
def list_events(
    orgId: str,
    db: Session = Depends(get_db),
    current_user: TokenPayload = Depends(deps.get_current_user),
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(20, ge=1, le=100, description="Items per page"),
):
    """Retrieves a paginated list of all events belonging to a specific organization."""
    if current_user.org_id != orgId:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized"
        )

    skip = (page - 1) * limit
    # NEW: Calling the inherited method from CRUDBase
    events = crud_event.event.get_multi_by_organization(
        db, org_id=orgId, skip=skip, limit=limit
    )
    total_events = crud_event.event.get_events_count(db=db, org_id=orgId)

    return {
        "data": events,
        "pagination": {
            "totalItems": total_events,
            "totalPages": math.ceil(total_events / limit),
            "currentPage": page,
        },
    }


@router.get("/organizations/{orgId}/events/{eventId}", response_model=EventSchema)
def get_event_by_id(
    orgId: str,
    eventId: str,
    db: Session = Depends(get_db),
    current_user: TokenPayload = Depends(deps.get_current_user),
):
    """Get a specific event by its ID."""
    if current_user.org_id != orgId:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized"
        )

    # NEW: Calling the inherited method from CRUDBase
    event = crud_event.event.get(db, id=eventId)
    if not event or event.organization_id != orgId:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Event not found"
        )

    return event


@router.patch("/organizations/{orgId}/events/{eventId}", response_model=EventSchema)
def update_event(
    orgId: str,
    eventId: str,
    event_in: EventUpdate,
    db: Session = Depends(get_db),
    current_user: TokenPayload = Depends(deps.get_current_user),
):
    """Partially update an event."""
    if current_user.org_id != orgId:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized"
        )

    event = crud_event.event.get(db, id=eventId)
    if not event or event.organization_id != orgId:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Event not found"
        )

    # NEW: Calling the inherited method from CRUDBase
    return crud_event.event.update(
        db, db_obj=event, obj_in=event_in, user_id=current_user.sub
    )


@router.delete(
    "/organizations/{orgId}/events/{eventId}", status_code=status.HTTP_204_NO_CONTENT
)
def delete_event(
    orgId: str,
    eventId: str,
    db: Session = Depends(get_db),
    current_user: TokenPayload = Depends(deps.get_current_user),
):
    """Soft-deletes an event by archiving it."""
    if current_user.org_id != orgId:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized"
        )

    event = crud_event.event.get(db, id=eventId)
    if not event or event.organization_id != orgId:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Event not found"
        )

    # NEW: Calling the inherited method from CRUDBase
    crud_event.event.archive(db, id=eventId, user_id=current_user.sub)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ADD THIS NEW ENDPOINT
@router.post(
    "/organizations/{orgId}/events/{eventId}/publish", response_model=EventSchema
)
def publish_event(
    orgId: str,
    eventId: str,
    db: Session = Depends(get_db),
    current_user: TokenPayload = Depends(deps.get_current_user),
):
    """
    Publish a draft event, making it publicly visible.
    """
    if current_user.org_id != orgId:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized"
        )

    event_to_publish = crud_event.event.get(db, id=eventId)
    if not event_to_publish or event_to_publish.organization_id != orgId:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Event not found"
        )

    if event_to_publish.status != "draft":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot publish event with status '{event_to_publish.status}'",
        )

    return crud_event.event.publish(
        db, db_obj=event_to_publish, user_id=current_user.sub
    )


# --- ADD THE NEW `get_event_history` ENDPOINT ---
@router.get(
    "/organizations/{orgId}/events/{eventId}/history",
    response_model=List[DomainEventSchema],
)
def get_event_history(
    orgId: str,
    eventId: str,
    db: Session = Depends(get_db),
    current_user: TokenPayload = Depends(deps.get_current_user),
):
    """
    Retrieves a chronological log of all domain events for a specific event.
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

    return crud_domain_event.domain_event.get_for_event(db, event_id=eventId)


# ADD THIS NEW ENDPOINT
@router.get(
    "/organizations/{orgId}/events/{eventId}/sync-bundle",
    response_model=EventSyncBundle,
)
def get_event_sync_bundle(
    orgId: str,
    eventId: str,
    db: Session = Depends(get_db),
    current_user: TokenPayload = Depends(deps.get_current_user),
):
    """
    Retrieves all necessary data for a single event in one payload,
    optimized for offline client synchronization.
    """
    if current_user.org_id != orgId:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized"
        )

    event_bundle_data = crud_event.event.get_sync_bundle(db, event_id=eventId)

    if not event_bundle_data or event_bundle_data.organization_id != orgId:
        raise HTTPException(
            status_code=status.HTTP_4_NOT_FOUND, detail="Event not found"
        )

    # We need to manually gather the unique speakers from all sessions
    all_speakers = []
    if event_bundle_data.sessions:
        speaker_ids = set()
        for session in event_bundle_data.sessions:
            for speaker in session.speakers:
                if speaker.id not in speaker_ids:
                    all_speakers.append(speaker)
                    speaker_ids.add(speaker.id)

    return EventSyncBundle(
        event=event_bundle_data,
        sessions=event_bundle_data.sessions,
        speakers=all_speakers,
        venue=event_bundle_data.venue,
    )
