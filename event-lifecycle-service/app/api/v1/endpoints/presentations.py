# app/api/v1/endpoints/presentations.py

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api import deps
from app.db.session import get_db
from app.crud import crud_session
from app.schemas.token import TokenPayload
from app.schemas.presentation import (
    PresentationUploadRequest,
    PresentationUploadResponse,
    PresentationProcessRequest,
)
from app.tasks import process_presentation
from app.core.s3 import generate_presigned_post

router = APIRouter(tags=["Presentations"])


@router.post(
    "/organizations/{orgId}/events/{eventId}/sessions/{sessionId}/presentation/upload-request",
    response_model=PresentationUploadResponse,
)
def request_presentation_upload(
    orgId: str,
    eventId: str,
    sessionId: str,
    upload_request: PresentationUploadRequest,
    db: Session = Depends(get_db),
    current_user: TokenPayload = Depends(deps.get_current_user),
):
    """
    Step 1: Client requests permission to upload a presentation file.
    The server returns a secure, pre-signed URL for a direct-to-S3 upload.
    """
    if current_user.org_id != orgId:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized for this organization",
        )

    # --- FIX: Fetch session by its ID first ---
    session = crud_session.session.get(db=db, id=sessionId)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Session not found"
        )

    # --- FIX: Now, verify the session belongs to the correct event ---
    if session.event_id != eventId:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Session does not belong to the specified event.",
        )

    s3_key = f"uploads/presentations/{sessionId}/{upload_request.filename}"
    presigned_data = generate_presigned_post(
        object_name=s3_key, content_type=upload_request.content_type
    )

    if not presigned_data:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not generate upload URL",
        )

    return PresentationUploadResponse(
        url=presigned_data["url"], fields=presigned_data["fields"], s3_key=s3_key
    )


@router.post(
    "/organizations/{orgId}/events/{eventId}/sessions/{sessionId}/presentation/process",
    status_code=status.HTTP_202_ACCEPTED,
)
def process_uploaded_presentation(
    orgId: str,
    eventId: str,
    sessionId: str,
    process_request: PresentationProcessRequest,
    db: Session = Depends(get_db),
    current_user: TokenPayload = Depends(deps.get_current_user),
):
    """
    Step 2: Client notifies the server that the S3 upload is complete.
    The server dispatches the background job to process the file.
    """
    if current_user.org_id != orgId:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized for this organization",
        )

    # --- FIX: Fetch session by its ID first ---
    session = crud_session.session.get(db=db, id=sessionId)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Session not found"
        )

    # --- FIX: Now, verify the session belongs to the correct event ---
    if session.event_id != eventId:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Session does not belong to the specified event.",
        )

    process_presentation.delay(session_id=sessionId, s3_key=process_request.s3_key)

    return {"message": "Presentation processing has been initiated."}
