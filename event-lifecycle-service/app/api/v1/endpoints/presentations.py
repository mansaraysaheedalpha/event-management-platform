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
from app.core.s3 import generate_presigned_post  # We'll need to add this helper

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
            status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized"
        )

    session = crud_session.session.get(db=db, event_id=eventId, session_id=sessionId)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Session not found"
        )

    # Generate the pre-signed URL for the client to use
    s3_key = f"uploads/presentations/{sessionId}/{upload_request.filename}"
    presigned_data = generate_presigned_post(
        object_name=s3_key, content_type=upload_request.content_type
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
            status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized"
        )

    session = crud_session.session.get(db=db, event_id=eventId, session_id=sessionId)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Session not found"
        )

    # Dispatch the processing to the Celery worker with the S3 key
    process_presentation.delay(session_id=sessionId, s3_key=process_request.s3_key)

    return {"message": "Presentation processing has been initiated."}
