# app/api/v1/endpoints/presentations.py file:

import re
import json
import logging
from fastapi import APIRouter, Depends, HTTPException, status, Security, Request
from sqlalchemy.orm import Session as DBSession
from botocore.exceptions import ClientError
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.api import deps
from app.db.session import get_db
from app.db.redis import get_redis_client
from app.crud import crud_session, crud_presentation, crud_registration, crud_event
from app.schemas.token import TokenPayload
from app.schemas.presentation import (
    PresentationUploadRequest,
    PresentationUploadResponse,
    PresentationProcessRequest,
    Presentation as PresentationSchema,
    DownloadToggleRequest,
    DownloadToggleResponse,
    DownloadUrlResponse,
)
from app.tasks import process_presentation
from app.core.s3 import generate_presigned_post, generate_presigned_download_url
from app.core.config import settings
from app.models.speaker import Speaker
from app.models.session_speaker import session_speaker_association

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Presentations"])

# Rate limiter instance (uses the app-level limiter)
limiter = Limiter(key_func=get_remote_address)

# Allowed content types for presentation uploads
ALLOWED_CONTENT_TYPES = {"application/pdf"}

# Regex pattern for sanitizing filenames
SAFE_FILENAME_PATTERN = re.compile(r"^[\w\-. ]+$")


# Roles that can manage presentations for any session in their organization
PRESENTATION_MANAGEMENT_ROLES = {"OWNER", "ADMIN"}

# Permissions that grant presentation management access
PRESENTATION_MANAGEMENT_PERMISSIONS = {"content:manage"}


def is_user_speaker_for_session(db: DBSession, user_id: str, session_id: str) -> bool:
    """
    Check if a user is assigned as a speaker for a specific session.

    This enables speakers to manage their own presentations without
    requiring high-level organization roles. The speaker must have their
    user_id field populated and be linked to the session.

    Args:
        db: Database session
        user_id: The platform user ID
        session_id: The session ID

    Returns:
        True if the user is a speaker for this session
    """
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
    return speaker is not None


def can_manage_presentation(
    db: DBSession,
    current_user: TokenPayload,
    org_id: str,
    session_id: str,
) -> tuple[bool, str]:
    """
    Determine if a user can manage presentations for a session.

    Authorization rules:
    1. OWNER, ADMIN roles can manage any presentation in their org
    2. Users with 'content:manage' permission can manage any presentation
    3. Speakers assigned to the session can manage their own presentations
       (either via SPEAKER role in org, or external speakers linked via user_id)

    Args:
        db: Database session
        current_user: The authenticated user's token payload
        org_id: The organization ID
        session_id: The session ID

    Returns:
        Tuple of (is_authorized, reason)
    """
    # Check 1: Must belong to the organization (if they have an org_id)
    if current_user.org_id and current_user.org_id != org_id:
        return False, "Not authorized for this organization"

    # Check 2: High-level roles (OWNER, ADMIN) can manage anything
    if current_user.role in PRESENTATION_MANAGEMENT_ROLES:
        return True, "authorized_by_role"

    # Check 3: Users with content:manage permission can manage anything
    if current_user.permissions:
        if any(p in PRESENTATION_MANAGEMENT_PERMISSIONS for p in current_user.permissions):
            return True, "authorized_by_permission"

    # Check 4: Speakers (org role or external) can manage their assigned sessions
    # This covers both SPEAKER role members and external speakers linked via user_id
    if is_user_speaker_for_session(db, current_user.sub, session_id):
        return True, "authorized_as_speaker"

    return False, "Not authorized to manage this presentation"


def validate_session_access(
    db: DBSession,
    org_id: str,
    event_id: str,
    session_id: str,
) -> None:
    """
    Validate that the session exists, belongs to the event, and the event
    belongs to the organization. Raises HTTPException if validation fails.

    This is critical for security - without this check, an attacker from OrgA
    could potentially access/manipulate presentations in OrgB by crafting URLs.
    """
    # First validate the event belongs to the organization
    event = crud_event.event.get(db=db, id=event_id)
    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Event not found.",
        )
    if event.organization_id != org_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Event not found in this organization.",
        )

    # Then validate the session belongs to the event
    session = crud_session.session.get(db=db, id=session_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found.",
        )
    if session.event_id != event_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found in this event.",
        )


def sanitize_filename(filename: str) -> str:
    """
    Sanitize filename to prevent path traversal attacks.
    Removes directory separators and validates characters.
    """
    # Remove any path components (directory traversal prevention)
    filename = filename.replace("\\", "/").split("/")[-1]

    # Remove leading/trailing whitespace and dots
    filename = filename.strip().strip(".")

    if not filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid filename",
        )

    # Validate filename contains only safe characters
    if not SAFE_FILENAME_PATTERN.match(filename):
        # Replace unsafe characters with underscores
        filename = re.sub(r"[^\w\-. ]", "_", filename)

    # Limit filename length
    if len(filename) > 200:
        name, ext = filename.rsplit(".", 1) if "." in filename else (filename, "")
        filename = name[:195] + ("." + ext if ext else "")

    return filename


def validate_content_type(content_type: str) -> None:
    """Validate that the content type is allowed."""
    if content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Content type '{content_type}' is not allowed. Only PDF files are supported.",
        )


@router.post(
    "/organizations/{orgId}/events/{eventId}/sessions/{sessionId}/presentation/upload-request",
    response_model=PresentationUploadResponse,
)
@limiter.limit("5/hour")  # Rate limit: 5 upload requests per hour per IP
def request_presentation_upload(
    request: Request,  # Required for rate limiting
    orgId: str,
    eventId: str,
    sessionId: str,
    upload_request: PresentationUploadRequest,
    db: DBSession = Depends(get_db),
    current_user: TokenPayload = Depends(deps.get_current_user),
):
    """
    Step 1: Client requests permission to upload a presentation file.
    The server returns a secure, pre-signed URL for a direct-to-S3 upload.

    Security:
    - Only OWNER/ADMIN roles, users with content:manage permission, or
      session speakers can upload presentations
    - Only PDF files are allowed
    - Filenames are sanitized to prevent path traversal
    - File size is limited to 100MB
    """
    # Authorization check
    is_authorized, reason = can_manage_presentation(db, current_user, orgId, sessionId)
    if not is_authorized:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=reason,
        )

    # Validate content type (only PDF allowed)
    validate_content_type(upload_request.content_type)

    # Sanitize filename to prevent path traversal
    safe_filename = sanitize_filename(upload_request.filename)

    # SECURITY: Validate event belongs to org and session belongs to event
    validate_session_access(db, orgId, eventId, sessionId)

    # Use sanitized filename in S3 key
    s3_key = f"uploads/presentations/{sessionId}/{safe_filename}"
    try:
        presigned_data = generate_presigned_post(
            object_name=s3_key, content_type=upload_request.content_type
        )
    except ClientError as e:
        logger.error(f"S3 presigned post error for session {sessionId}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not generate upload URL. Please try again.",
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
@limiter.limit("5/hour")  # Rate limit: 5 process requests per hour per IP
def process_uploaded_presentation(
    request: Request,  # Required for rate limiting
    orgId: str,
    eventId: str,
    sessionId: str,
    process_request: PresentationProcessRequest,
    db: DBSession = Depends(get_db),
    current_user: TokenPayload = Depends(deps.get_current_user),
):
    """
    Step 2: Client notifies the server that the S3 upload is complete.
    The server dispatches the background job to process the file.

    Security:
    - Only OWNER/ADMIN roles, users with content:manage permission, or
      session speakers can trigger processing
    """
    # Authorization check
    is_authorized, reason = can_manage_presentation(db, current_user, orgId, sessionId)
    if not is_authorized:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=reason,
        )

    # SECURITY: Validate event belongs to org and session belongs to event
    validate_session_access(db, orgId, eventId, sessionId)

    # SECURITY: Validate s3_key belongs to this session to prevent cross-session content injection
    # Expected format: uploads/presentations/{sessionId}/{filename}
    expected_prefix = f"uploads/presentations/{sessionId}/"
    if not process_request.s3_key.startswith(expected_prefix):
        logger.warning(
            f"User {current_user.sub} attempted to process invalid s3_key for session {sessionId}: {process_request.s3_key}"
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid S3 key for this session.",
        )

    # Extract original filename from s3_key for download feature
    original_filename = process_request.s3_key.split("/")[-1] if "/" in process_request.s3_key else "presentation.pdf"

    process_presentation.delay(
        session_id=sessionId,
        s3_key=process_request.s3_key,
        user_id=current_user.sub,
        original_filename=original_filename,
    )

    return {"message": "Presentation processing has been initiated."}


@router.get(
    "/organizations/{orgId}/events/{eventId}/sessions/{sessionId}/presentation",
    response_model=PresentationSchema,
)
@limiter.limit("60/minute")  # Rate limit: 60 requests per minute (allows polling)
def get_presentation_by_session(
    request: Request,  # Required for rate limiting
    orgId: str,
    eventId: str,
    sessionId: str,
    db: DBSession = Depends(get_db),
    token_payload: TokenPayload | None = Depends(deps.get_current_user_optional),
    api_key: str | None = Security(deps.get_internal_api_key_optional, scopes=[]),
):
    """
    Get presentation details for a specific session.
    This is used by the frontend to poll for the presentation status and retrieve the final slide URLs.

    Authentication: JWT token OR internal API key required.
    """
    if not token_payload and not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )

    # SECURITY: Validate event belongs to org and session belongs to event
    validate_session_access(db, orgId, eventId, sessionId)

    presentation = crud_presentation.presentation.get_by_session(
        db=db, session_id=sessionId
    )

    if not presentation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Presentation not found or is still processing.",
        )

    return presentation


# ============================================================================
# DOWNLOAD FEATURE ENDPOINTS
# ============================================================================


@router.post(
    "/organizations/{orgId}/events/{eventId}/sessions/{sessionId}/presentation/download/toggle",
    response_model=DownloadToggleResponse,
)
@limiter.limit("20/hour")  # Rate limit: 20 toggle requests per hour per IP
def toggle_presentation_download(
    request: Request,  # Required for rate limiting
    orgId: str,
    eventId: str,
    sessionId: str,
    toggle_request: DownloadToggleRequest,
    db: DBSession = Depends(get_db),
    current_user: TokenPayload = Depends(deps.get_current_user),
):
    """
    Toggle download availability for a presentation.
    When enabled, registered attendees can download the original presentation file.

    Authorization: Only OWNER/ADMIN roles, users with content:manage permission,
    or session speakers can toggle download.
    """
    # Authorization check
    is_authorized, reason = can_manage_presentation(db, current_user, orgId, sessionId)
    if not is_authorized:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=reason,
        )

    # SECURITY: Validate event belongs to org and session belongs to event
    validate_session_access(db, orgId, eventId, sessionId)

    presentation = crud_presentation.presentation.get_by_session(
        db=db, session_id=sessionId
    )

    if not presentation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Presentation not found. Upload a presentation first.",
        )

    if presentation.status != "ready":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot toggle download for a presentation that is not ready.",
        )

    # Update download_enabled
    crud_presentation.presentation.update(
        db, db_obj=presentation, obj_in={"download_enabled": toggle_request.enabled}
    )

    # Publish Redis event for real-time notification
    try:
        redis_client = get_redis_client()
        message_payload = {
            "sessionId": sessionId,
            "downloadEnabled": toggle_request.enabled,
            "filename": presentation.original_filename,
        }
        redis_client.publish("presentation-download-events", json.dumps(message_payload))
        logger.info(f"Published download toggle event for session {sessionId}: enabled={toggle_request.enabled}")
    except Exception as e:
        logger.error(f"Failed to publish download toggle to Redis: {e}")
        # Don't fail the request if Redis publish fails

    action = "enabled" if toggle_request.enabled else "disabled"
    return DownloadToggleResponse(
        download_enabled=toggle_request.enabled,
        message=f"Presentation download has been {action} for attendees.",
    )


@router.get(
    "/organizations/{orgId}/events/{eventId}/sessions/{sessionId}/presentation/download-url",
    response_model=DownloadUrlResponse,
)
@limiter.limit("10/hour")  # Rate limit: 10 download URL requests per hour per IP
def get_presentation_download_url(
    request: Request,  # Required for rate limiting
    orgId: str,
    eventId: str,
    sessionId: str,
    db: DBSession = Depends(get_db),
    current_user: TokenPayload = Depends(deps.get_current_user),
):
    """
    Get a time-limited signed URL to download the presentation.
    The URL expires in 5 minutes for security.

    Authorization:
    - User must be authenticated
    - OWNER/ADMIN roles and content:manage permission users can always download
    - Session speakers can always download their presentations
    - Registered attendees can download only when download_enabled is true
    """
    # SECURITY: Validate event belongs to org and session belongs to event
    validate_session_access(db, orgId, eventId, sessionId)

    # Check authorization level - can_manage already checks speaker status internally
    can_manage, auth_reason = can_manage_presentation(db, current_user, orgId, sessionId)

    # Managers (including speakers via auth_reason) can always access; others need registration
    if not can_manage:
        # Check if user is registered for this event with an active registration
        registration = crud_registration.registration.get_by_user_or_email(
            db=db, user_id=current_user.sub, event_id=eventId
        )
        if not registration:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You must be registered for this event to download presentations.",
            )
        # Verify registration is active (not cancelled or archived)
        if registration.status == "cancelled" or registration.is_archived == "true":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Your registration is no longer active.",
            )

    presentation = crud_presentation.presentation.get_by_session(
        db=db, session_id=sessionId
    )

    if not presentation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Presentation not found.",
        )

    if presentation.status != "ready":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Presentation is not ready for download.",
        )

    # Check if download is enabled (managers, including speakers, can always download)
    if not can_manage and not presentation.download_enabled:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Download is not enabled for this presentation.",
        )

    if not presentation.original_file_key:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Original presentation file not available.",
        )

    # Generate signed download URL (expires in 5 minutes)
    expires_in = 300
    try:
        download_url = generate_presigned_download_url(
            object_key=presentation.original_file_key,
            filename=presentation.original_filename or "presentation.pdf",
            expires_in=expires_in,
        )
    except ClientError as e:
        logger.error(f"Failed to generate download URL for session {sessionId}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not generate download URL. Please try again.",
        )

    logger.info(
        f"Generated download URL for user {current_user.sub}, session {sessionId}"
    )

    return DownloadUrlResponse(
        url=download_url,
        filename=presentation.original_filename or "presentation.pdf",
        expires_in=expires_in,
    )
