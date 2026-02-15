# app/api/v1/endpoints/check_in.py
"""
Check-in configuration and offline-support endpoints for scanner apps.

Provides:
- Configuration data (QR format version, offline support status)
- Verification key for offline QR validation (organizer-only, HMAC secret)
- Attendee manifest for offline check-in caching
"""

from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.api import deps
from app.db.session import get_db
from app.schemas.token import TokenPayload
from app.crud import crud_event
from app.crud.ticket_crud import ticket_crud

router = APIRouter(tags=["Check-in"])


# ============================================
# Response Models
# ============================================


class CheckInConfig(BaseModel):
    """Configuration response for check-in scanner apps."""

    qr_format: str
    version: int
    event_id: str
    supports_offline: bool


class VerificationKeyResponse(BaseModel):
    """HMAC signing key for offline QR verification.

    WARNING: This is a symmetric secret. Protect this endpoint with
    organizer-level auth. When upgraded to RS256, the public key
    can be served without auth restrictions.
    """

    key: str
    algorithm: str


class ManifestAttendee(BaseModel):
    """Lightweight attendee entry for offline manifest."""

    ticketCode: str
    attendeeName: str
    ticketType: str
    status: str


class CheckInManifest(BaseModel):
    """Attendee manifest for offline check-in caching."""

    eventId: str
    generatedAt: str
    totalTickets: int
    attendees: List[ManifestAttendee]


# ============================================
# Endpoints
# ============================================


@router.get(
    "/events/{event_id}/check-in/config",
    response_model=CheckInConfig,
)
def get_check_in_config(
    event_id: str,
    db: Session = Depends(get_db),
    current_user: TokenPayload = Depends(deps.get_current_user),
):
    """Return QR code configuration for a scanner app.

    The scanner app calls this on startup to learn:
    - What QR format to expect (jwt_hs256 for v2, pipe_delimited for v1)
    - Whether offline verification is supported (requires RS256 upgrade)
    - The event ID to validate against scanned QR claims

    Currently uses HS256 (server-side verification only).
    When upgraded to RS256 with public key distribution,
    supports_offline will be set to True and a public_key field
    will be included in the response.
    """
    event = crud_event.event.get(db, id=event_id)
    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Event not found",
        )

    return CheckInConfig(
        qr_format="jwt_hs256",
        version=2,
        event_id=event_id,
        supports_offline=False,
    )


@router.get(
    "/events/{event_id}/check-in/verification-key",
    response_model=VerificationKeyResponse,
)
def get_check_in_verification_key(
    event_id: str,
    db: Session = Depends(get_db),
    current_user: TokenPayload = Depends(deps.get_current_user),
):
    """Get the verification key for offline QR code checking.

    Returns the HMAC signing key so scanner apps can verify QR codes
    without calling the server. This endpoint MUST be protected with
    organizer-level authentication because HMAC keys are symmetric
    secrets -- anyone with the key can forge QR codes.

    When upgraded to RS256, only the public key will be returned and
    this endpoint can be relaxed to allow any authenticated staff.
    """
    # Verify event exists and user has access
    event = crud_event.event.get(db, id=event_id)
    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Event not found",
        )

    # Authorization: only organizers from the same org can access the key
    user_org_id = current_user.org_id
    if not user_org_id or user_org_id != event.organization_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only event organizers can access the verification key",
        )

    from app.services.ticket_management.qr_signing import get_signing_key_for_event

    return VerificationKeyResponse(
        key=get_signing_key_for_event(event_id),
        algorithm="HS256",
    )


@router.get(
    "/events/{event_id}/check-in/manifest",
    response_model=CheckInManifest,
)
def get_check_in_manifest(
    event_id: str,
    db: Session = Depends(get_db),
    current_user: TokenPayload = Depends(deps.get_current_user),
):
    """Get attendee manifest for offline check-in caching.

    Returns a lightweight list of all ticket holders for an event,
    suitable for caching on scanner devices for offline check-in.
    Includes ticket codes, attendee names, ticket types, and statuses.

    Limited to 10,000 tickets per request. For larger events, implement
    pagination or delta-sync in a future iteration.
    """
    # Verify event exists
    event = crud_event.event.get(db, id=event_id)
    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Event not found",
        )

    # Authorization: only organizers from the same org can access the manifest
    user_org_id = current_user.org_id
    if not user_org_id or user_org_id != event.organization_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only event organizers can access the attendee manifest",
        )

    tickets, total = ticket_crud.get_by_event(db, event_id, limit=10000)

    attendees = [
        ManifestAttendee(
            ticketCode=t.ticket_code,
            attendeeName=t.attendee_name,
            ticketType=t.ticket_type.name if t.ticket_type else "General",
            status=t.status,
        )
        for t in tickets
    ]

    return CheckInManifest(
        eventId=event_id,
        generatedAt=datetime.now(timezone.utc).isoformat(),
        totalTickets=total,
        attendees=attendees,
    )
