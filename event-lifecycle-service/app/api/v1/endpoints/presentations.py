#app/api/v1/endpoints/presentations.py file:

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from botocore.exceptions import ClientError

from app.api import deps
from app.db.session import get_db
from app.crud import crud_session, crud_presentation
from app.schemas.token import TokenPayload
from app.schemas.presentation import (
    PresentationUploadRequest,
    PresentationUploadResponse,
    PresentationProcessRequest,
    Presentation as PresentationSchema,
)
from app.tasks import process_presentation
from app.core.s3 import generate_presigned_post
from app.core.config import settings

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
    # if current_user.org_id != orgId:
    #     raise HTTPException(
    #         status_code=status.HTTP_403_FORBIDDEN,
    #         detail="Not authorized for this organization",
    #     )

    session = crud_session.session.get(db=db, id=sessionId)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Session not found"
        )

    if session.event_id != eventId:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Session does not belong to the specified event.",
        )

    s3_key = f"uploads/presentations/{sessionId}/{upload_request.filename}"
    try:
        presigned_data = generate_presigned_post(
            object_name=s3_key, content_type=upload_request.content_type
        )
    except ClientError as e:
        # Temporarily return the specific S3 error for debugging
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"S3 Error: {e}",
        )

    if not presigned_data:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not generate upload URL (no data from S3).",
        )

    upload_url = presigned_data["url"]

    # For local dev, the presigned URL is for 'minio:9000', which is not
    # accessible from the user's browser. We replace it with the public-facing
    # 'localhost:9000' before sending it to the client.
    if settings.AWS_S3_ENDPOINT_URL and "minio:9000" in upload_url:
        upload_url = upload_url.replace("minio:9000", "localhost:9000")

    return PresentationUploadResponse(
        url=upload_url, fields=presigned_data["fields"], s3_key=s3_key
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
    # if current_user.org_id != orgId:
    #     raise HTTPException(
    #         status_code=status.HTTP_403_FORBIDDEN,
    #         detail="Not authorized for this organization",
    #     )

    session = crud_session.session.get(db=db, id=sessionId)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Session not found"
        )

    if session.event_id != eventId:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Session does not belong to the specified event.",
        )

    process_presentation.delay(session_id=sessionId, s3_key=process_request.s3_key)

    return {"message": "Presentation processing has been initiated."}


@router.get(
    "/organizations/{orgId}/events/{eventId}/sessions/{sessionId}/presentation",
    response_model=PresentationSchema,
)
def get_presentation_by_session(
    orgId: str,
    eventId: str,
    sessionId: str,
    db: Session = Depends(get_db),
    current_user: TokenPayload = Depends(deps.get_current_user),
):
    """
    Get presentation details for a specific session.
    This is used by the frontend to poll for the presentation status and retrieve the final slide URLs.
    """
    # if current_user.org_id != orgId:
    #     raise HTTPException(
    #         status_code=status.HTTP_403_FORBIDDEN,
    #         detail="Not authorized for this organization",
    #     )

    session = crud_session.session.get(db=db, id=sessionId)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Session not found"
        )

    if session.event_id != eventId:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Session does not belong to the specified event.",
        )

    presentation = crud_presentation.presentation.get_by_session(
        db=db, session_id=sessionId
    )

    if not presentation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Presentation not found or is still processing.",
        )

    return presentation