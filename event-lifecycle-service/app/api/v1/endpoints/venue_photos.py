# app/api/v1/endpoints/venue_photos.py
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status, Response
from sqlalchemy.orm import Session

from app.api import deps
from app.db.session import get_db
from app.crud.crud_venue import venue as crud_venue_obj
from app.crud.crud_venue_photo import venue_photo as crud_photo
from app.core.s3 import generate_presigned_post, get_s3_client
from app.core.config import settings
from app.schemas.venue_photo import (
    PhotoUploadRequest,
    PhotoUploadResponse,
    PhotoUploadComplete,
    VenuePhotoUpdate,
    VenuePhoto,
    PhotoReorderRequest,
)
from app.schemas.token import TokenPayload

router = APIRouter(tags=["Venue Photos"])

ALLOWED_PHOTO_TYPES = {"image/jpeg", "image/png", "image/webp"}
MAX_PHOTO_SIZE = 10 * 1024 * 1024  # 10MB
MAX_PHOTOS_PER_VENUE = 10


def _sanitize_filename(filename: str) -> str:
    """Strip path components and reject dangerous filenames."""
    from app.utils.sanitize import sanitize_filename
    try:
        return sanitize_filename(filename)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid filename")


def _verify_venue_ownership(db: Session, org_id: str, venue_id: str):
    venue = crud_venue_obj.get(db, id=venue_id)
    if not venue or venue.organization_id != org_id or venue.is_archived:
        raise HTTPException(status_code=404, detail="Venue not found")
    return venue


@router.post(
    "/organizations/{orgId}/venues/{venueId}/photos/upload-request",
    response_model=PhotoUploadResponse,
)
def request_photo_upload(
    orgId: str,
    venueId: str,
    upload_req: PhotoUploadRequest,
    db: Session = Depends(get_db),
    current_user: TokenPayload = Depends(deps.get_current_user),
):
    """Step 1: Request a presigned upload URL for a venue photo."""
    if current_user.org_id != orgId:
        raise HTTPException(status_code=403, detail="Not authorized")
    _verify_venue_ownership(db, orgId, venueId)

    if upload_req.content_type not in ALLOWED_PHOTO_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid content type. Allowed: {', '.join(ALLOWED_PHOTO_TYPES)}",
        )

    # Check photo limit
    count = crud_photo.count_by_venue(db, venue_id=venueId)
    if count >= MAX_PHOTOS_PER_VENUE:
        raise HTTPException(
            status_code=409,
            detail=f"Maximum of {MAX_PHOTOS_PER_VENUE} photos per venue reached",
        )

    safe_filename = _sanitize_filename(upload_req.filename)
    s3_key = f"venue-images/{venueId}/{safe_filename}"
    presigned_data = generate_presigned_post(
        object_name=s3_key,
        content_type=upload_req.content_type,
        max_size_bytes=MAX_PHOTO_SIZE,
        public_read=True,
    )
    if not presigned_data:
        raise HTTPException(status_code=500, detail="Could not generate upload URL")

    return PhotoUploadResponse(
        upload_url=presigned_data["url"],
        upload_fields=presigned_data["fields"],
        s3_key=s3_key,
    )


@router.post(
    "/organizations/{orgId}/venues/{venueId}/photos/upload-complete",
    response_model=VenuePhoto,
    status_code=status.HTTP_201_CREATED,
)
def complete_photo_upload(
    orgId: str,
    venueId: str,
    complete_req: PhotoUploadComplete,
    db: Session = Depends(get_db),
    current_user: TokenPayload = Depends(deps.get_current_user),
):
    """Step 2: Confirm upload and create photo record."""
    if current_user.org_id != orgId:
        raise HTTPException(status_code=403, detail="Not authorized")
    _verify_venue_ownership(db, orgId, venueId)

    # Validate s3_key belongs to this venue (prevent IDOR)
    expected_prefix = f"venue-images/{venueId}/"
    if not complete_req.s3_key.startswith(expected_prefix):
        raise HTTPException(status_code=400, detail="Invalid s3_key for this venue")

    # H-01: Re-check photo limit at commit time to prevent race condition
    count = crud_photo.count_by_venue(db, venue_id=venueId)
    if count >= MAX_PHOTOS_PER_VENUE:
        # Best-effort cleanup of the orphaned S3 object
        try:
            s3_client = get_s3_client()
            s3_client.delete_object(
                Bucket=settings.AWS_S3_BUCKET_NAME, Key=complete_req.s3_key
            )
        except Exception:
            pass
        raise HTTPException(
            status_code=409,
            detail=f"Maximum of {MAX_PHOTOS_PER_VENUE} photos per venue reached",
        )

    return crud_photo.create(
        db,
        venue_id=venueId,
        obj_in=complete_req.model_dump(),
    )


@router.patch(
    "/organizations/{orgId}/venues/{venueId}/photos/{photoId}",
    response_model=VenuePhoto,
)
def update_photo(
    orgId: str,
    venueId: str,
    photoId: str,
    photo_in: VenuePhotoUpdate,
    db: Session = Depends(get_db),
    current_user: TokenPayload = Depends(deps.get_current_user),
):
    """Update photo metadata."""
    if current_user.org_id != orgId:
        raise HTTPException(status_code=403, detail="Not authorized")
    _verify_venue_ownership(db, orgId, venueId)
    photo = crud_photo.get(db, id=photoId)
    if not photo or photo.venue_id != venueId:
        raise HTTPException(status_code=404, detail="Photo not found")
    return crud_photo.update(
        db, db_obj=photo, obj_in=photo_in.model_dump(exclude_unset=True)
    )


@router.delete(
    "/organizations/{orgId}/venues/{venueId}/photos/{photoId}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_photo(
    orgId: str,
    venueId: str,
    photoId: str,
    db: Session = Depends(get_db),
    current_user: TokenPayload = Depends(deps.get_current_user),
):
    """Delete a photo (also deletes from S3)."""
    if current_user.org_id != orgId:
        raise HTTPException(status_code=403, detail="Not authorized")
    _verify_venue_ownership(db, orgId, venueId)
    photo = crud_photo.get(db, id=photoId)
    if not photo or photo.venue_id != venueId:
        raise HTTPException(status_code=404, detail="Photo not found")

    # H-03: Clear cover_photo_id if this is the cover photo
    venue = crud_venue_obj.get(db, id=venueId)
    if venue and venue.cover_photo_id == photoId:
        venue.cover_photo_id = None
        db.add(venue)

    s3_key = crud_photo.delete(db, id=photoId)
    if s3_key:
        try:
            s3_client = get_s3_client()
            s3_client.delete_object(
                Bucket=settings.AWS_S3_BUCKET_NAME, Key=s3_key
            )
        except Exception:
            pass  # S3 cleanup is best-effort

    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.patch(
    "/organizations/{orgId}/venues/{venueId}/photos/reorder",
    response_model=List[VenuePhoto],
)
def reorder_photos(
    orgId: str,
    venueId: str,
    reorder_req: PhotoReorderRequest,
    db: Session = Depends(get_db),
    current_user: TokenPayload = Depends(deps.get_current_user),
):
    """Reorder photos."""
    if current_user.org_id != orgId:
        raise HTTPException(status_code=403, detail="Not authorized")
    _verify_venue_ownership(db, orgId, venueId)
    return crud_photo.reorder(db, venue_id=venueId, photo_ids=reorder_req.photo_ids)
