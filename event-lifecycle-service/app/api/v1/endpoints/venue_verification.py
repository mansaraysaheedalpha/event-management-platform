# app/api/v1/endpoints/venue_verification.py
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api import deps
from app.db.session import get_db
from app.crud.crud_venue import venue as crud_venue_obj
from app.crud.crud_venue_verification import venue_verification as crud_verification
from app.core.s3 import generate_presigned_post
from app.schemas.venue_verification import (
    VerificationUploadRequest,
    VerificationUploadResponse,
    VerificationUploadComplete,
    VenueVerificationDocument,
)
from app.schemas.token import TokenPayload

router = APIRouter(tags=["Venue Verification"])

ALLOWED_VERIFICATION_TYPES = {"application/pdf", "image/jpeg", "image/png"}
MAX_VERIFICATION_SIZE = 20 * 1024 * 1024  # 20MB


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
    "/organizations/{orgId}/venues/{venueId}/verification/upload-request",
    response_model=VerificationUploadResponse,
)
def request_verification_upload(
    orgId: str,
    venueId: str,
    upload_req: VerificationUploadRequest,
    db: Session = Depends(get_db),
    current_user: TokenPayload = Depends(deps.get_current_user),
):
    """Request presigned URL for verification document upload."""
    if current_user.org_id != orgId:
        raise HTTPException(status_code=403, detail="Not authorized")
    _verify_venue_ownership(db, orgId, venueId)

    if upload_req.content_type not in ALLOWED_VERIFICATION_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid content type. Allowed: {', '.join(ALLOWED_VERIFICATION_TYPES)}",
        )

    safe_filename = _sanitize_filename(upload_req.filename)
    s3_key = f"venue-verification/{venueId}/{safe_filename}"
    presigned_data = generate_presigned_post(
        object_name=s3_key,
        content_type=upload_req.content_type,
        max_size_bytes=MAX_VERIFICATION_SIZE,
    )
    if not presigned_data:
        raise HTTPException(status_code=500, detail="Could not generate upload URL")

    return VerificationUploadResponse(
        upload_url=presigned_data["url"],
        upload_fields=presigned_data["fields"],
        s3_key=s3_key,
    )


@router.post(
    "/organizations/{orgId}/venues/{venueId}/verification/upload-complete",
    response_model=VenueVerificationDocument,
    status_code=status.HTTP_201_CREATED,
)
def complete_verification_upload(
    orgId: str,
    venueId: str,
    complete_req: VerificationUploadComplete,
    db: Session = Depends(get_db),
    current_user: TokenPayload = Depends(deps.get_current_user),
):
    """Confirm verification document upload."""
    if current_user.org_id != orgId:
        raise HTTPException(status_code=403, detail="Not authorized")
    _verify_venue_ownership(db, orgId, venueId)

    # Validate s3_key belongs to this venue (prevent IDOR)
    expected_prefix = f"venue-verification/{venueId}/"
    if not complete_req.s3_key.startswith(expected_prefix):
        raise HTTPException(status_code=400, detail="Invalid s3_key for this venue")

    return crud_verification.create(
        db,
        venue_id=venueId,
        obj_in=complete_req.model_dump(),
    )


@router.get(
    "/organizations/{orgId}/venues/{venueId}/verification",
    response_model=List[VenueVerificationDocument],
)
def list_verification_documents(
    orgId: str,
    venueId: str,
    db: Session = Depends(get_db),
    current_user: TokenPayload = Depends(deps.get_current_user),
):
    """List all verification documents for a venue."""
    if current_user.org_id != orgId:
        raise HTTPException(status_code=403, detail="Not authorized")
    _verify_venue_ownership(db, orgId, venueId)
    return crud_verification.get_multi_by_venue(db, venue_id=venueId)
