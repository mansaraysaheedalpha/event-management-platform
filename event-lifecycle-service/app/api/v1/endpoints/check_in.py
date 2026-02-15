# app/api/v1/endpoints/check_in.py
"""
Check-in configuration, offline-support, and bulk-sync endpoints.

Provides:
- Configuration data (QR format version, offline support status)
- Public key for offline QR verification (RS256)
- Attendee manifest for offline check-in caching
- Bulk sync endpoint for uploading offline check-ins
"""

import logging
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

logger = logging.getLogger(__name__)

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
    """RS256 public key for offline QR verification.

    This is a public key — safe to distribute to any authenticated
    scanner app. It cannot be used to forge QR codes.
    """

    key: str
    algorithm: str
    key_type: str


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


class BulkCheckInItem(BaseModel):
    """A single offline check-in to sync."""

    ticketCode: str
    checkedInBy: str
    checkedInAt: str
    location: Optional[str] = None


class BulkCheckInResult(BaseModel):
    """Result for a single check-in in a bulk sync."""

    ticketCode: str
    status: str  # "synced" | "already_checked_in" | "not_found" | "error"
    message: Optional[str] = None


class BulkCheckInResponse(BaseModel):
    """Response for bulk offline check-in sync."""

    synced: int
    conflicts: int
    errors: int
    details: List[BulkCheckInResult]


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
    - What QR format to expect (jwt_rs256 for v3, jwt_hs256 for v2)
    - Whether offline verification is supported (True with RS256 public keys)
    - The event ID to validate against scanned QR claims
    """
    event = crud_event.event.get(db, id=event_id)
    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Event not found",
        )

    return CheckInConfig(
        qr_format="jwt_rs256",
        version=3,
        event_id=event_id,
        supports_offline=True,
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
    """Get the RS256 public key for offline QR code verification.

    Returns the public key PEM so scanner apps can verify QR codes
    without calling the server. Public keys cannot forge QR codes,
    so this endpoint is safe for any authenticated event staff.
    """
    event = crud_event.event.get(db, id=event_id)
    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Event not found",
        )

    from app.services.ticket_management.qr_signing import get_signing_key_for_event

    return VerificationKeyResponse(
        key=get_signing_key_for_event(event_id),
        algorithm="RS256",
        key_type="public",
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
    Limited to 10,000 tickets per request.
    """
    event = crud_event.event.get(db, id=event_id)
    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Event not found",
        )

    # Authorization: only organizers from the same org
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


@router.post(
    "/events/{event_id}/check-in/bulk",
    response_model=BulkCheckInResponse,
)
def bulk_sync_check_ins(
    event_id: str,
    items: List[BulkCheckInItem],
    db: Session = Depends(get_db),
    current_user: TokenPayload = Depends(deps.get_current_user),
):
    """Sync offline check-ins back to the server.

    Accepts a batch of check-ins performed offline and processes them.
    Each item is handled independently — a failure in one doesn't
    block others. Returns per-item results so the scanner can
    clear its sync queue for successful items.
    """
    event = crud_event.event.get(db, id=event_id)
    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Event not found",
        )

    user_org_id = current_user.org_id
    if not user_org_id or user_org_id != event.organization_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only event organizers can sync check-ins",
        )

    synced = 0
    conflicts = 0
    errors = 0
    details: List[BulkCheckInResult] = []

    for item in items:
        try:
            ticket = ticket_crud.get_by_code(db, item.ticketCode, event_id)
            if not ticket:
                errors += 1
                details.append(BulkCheckInResult(
                    ticketCode=item.ticketCode,
                    status="not_found",
                    message="Ticket not found",
                ))
                continue

            if ticket.status == "checked_in":
                conflicts += 1
                details.append(BulkCheckInResult(
                    ticketCode=item.ticketCode,
                    status="already_checked_in",
                    message="Already checked in on server",
                ))
                continue

            ticket_crud.check_in(
                db,
                ticket.id,
                checked_in_by=item.checkedInBy,
                location=item.location,
            )
            synced += 1
            details.append(BulkCheckInResult(
                ticketCode=item.ticketCode,
                status="synced",
            ))

        except Exception as e:
            logger.warning(f"Bulk check-in error for {item.ticketCode}: {e}")
            errors += 1
            details.append(BulkCheckInResult(
                ticketCode=item.ticketCode,
                status="error",
                message="Check-in failed",
            ))

    return BulkCheckInResponse(
        synced=synced,
        conflicts=conflicts,
        errors=errors,
        details=details,
    )
