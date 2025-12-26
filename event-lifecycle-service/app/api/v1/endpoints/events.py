# app/api/v1/endpoints/events.py
import math
from typing import List
from fastapi import APIRouter, Depends, status, HTTPException, Query, Response
from sqlalchemy.orm import Session
from app.schemas.event_sync_bundle import EventSyncBundle
from app.schemas.event import ImageUploadRequest, ImageUploadResponse
from app.core.config import settings
from app.core.s3 import generate_presigned_post

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


@router.post(
    "/organizations/{orgId}/events/{eventId}/restore", response_model=EventSchema
)
def restore_event(
    orgId: str,
    eventId: str,
    db: Session = Depends(get_db),
    current_user: TokenPayload = Depends(deps.get_current_user),
):
    """
    Restores a soft-deleted (archived) event.
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

    if not event.is_archived:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Event is not archived",
        )

    return crud_event.event.restore(db, id=eventId, user_id=current_user.sub)


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


@router.post(
    "/organizations/{orgId}/events/{eventId}/unpublish", response_model=EventSchema
)
def unpublish_event(
    orgId: str,
    eventId: str,
    db: Session = Depends(get_db),
    current_user: TokenPayload = Depends(deps.get_current_user),
):
    """
    Unpublish a previously published event, reverting it to draft.
    """
    if current_user.org_id != orgId:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized"
        )

    event_to_unpublish = crud_event.event.get(db, id=eventId)
    if not event_to_unpublish or event_to_unpublish.organization_id != orgId:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Event not found"
        )

    if event_to_unpublish.status == "draft":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Event is already in draft status",
        )

    if event_to_unpublish.is_archived:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot unpublish an archived event",
        )

    return crud_event.event.unpublish(
        db, db_obj=event_to_unpublish, user_id=current_user.sub
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


# ✅ --- ADD THESE TWO NEW ENDPOINTS AT THE BOTTOM OF THE FILE ---


@router.post(
    "/organizations/{orgId}/events/{eventId}/image-upload-request",
    response_model=ImageUploadResponse,
)
def request_image_upload(
    orgId: str,
    eventId: str,
    upload_request: ImageUploadRequest,
    db: Session = Depends(get_db),
    current_user: TokenPayload = Depends(deps.get_current_user),
):
    """
    Step 1: Client requests to upload an event image.
    Server returns a secure, pre-signed URL for a direct-to-S3 upload.
    """
    if current_user.org_id != orgId:
        raise HTTPException(status_code=403, detail="Not authorized")

    event = crud_event.event.get(db, id=eventId)
    if not event or event.organization_id != orgId:
        raise HTTPException(status_code=404, detail="Event not found")

    s3_key = f"event-images/{eventId}/{upload_request.filename}"
    presigned_data = generate_presigned_post(
        object_name=s3_key, content_type=upload_request.content_type
    )

    if not presigned_data:
        raise HTTPException(status_code=500, detail="Could not generate upload URL")

    return ImageUploadResponse(
        url=presigned_data["url"], fields=presigned_data["fields"], s3_key=s3_key
    )


@router.post(
    "/organizations/{orgId}/events/{eventId}/image-upload-complete",
    response_model=EventSchema,
    status_code=status.HTTP_200_OK,
)
def complete_image_upload(
    orgId: str,
    eventId: str,
    s3_key: str,  # Sent as a query parameter
    db: Session = Depends(get_db),
    current_user: TokenPayload = Depends(deps.get_current_user),
):
    """
    Step 2: Client notifies server that upload is complete.
    Server updates the event record with the final S3 URL.
    """
    if current_user.org_id != orgId:
        raise HTTPException(status_code=403, detail="Not authorized")

    # Construct the permanent, public URL for the image
    bucket_name = settings.AWS_S3_BUCKET_NAME
    region = settings.AWS_S3_REGION
    public_url = f"https://{bucket_name}.s3.{region}.amazonaws.com/{s3_key}"

    updated_event = crud_event.event.update_image_url(
        db, event_id=eventId, image_url=public_url
    )

    if not updated_event:
        raise HTTPException(status_code=404, detail="Event not found after update")

    return updated_event
