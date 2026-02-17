# app/api/v1/endpoints/venue_admin.py
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api import deps
from app.db.session import get_db
from app.crud.crud_venue import venue as crud_venue_obj
from app.crud.crud_amenity import amenity as crud_amenity_obj
from app.schemas.venue import (
    Venue,
    VenueAdminApproveResponse,
    VenueAdminRejectResponse,
    AdminRejectRequest,
    AdminSuspendRequest,
    AdminVenueSuspendResponse,
    AdminRequestDocumentsRequest,
    AdminVerificationStatusUpdate,
)
from app.crud.crud_venue_verification import venue_verification as crud_verification
from app.schemas.amenity import (
    AmenityCategoryCreate,
    AmenityCategoryResponse,
    AmenityCreate,
    AmenityUpdate,
    AmenityResponse,
)
from app.schemas.token import TokenPayload

router = APIRouter(tags=["Venue Admin"])


def _require_admin(current_user: TokenPayload):
    """Verify the user has admin role."""
    if not current_user.role or current_user.role.lower() not in ("admin", "superadmin"):
        raise HTTPException(status_code=403, detail="Admin access required")


@router.get("/admin/venues")
def admin_list_venues(
    status: Optional[str] = None,
    domain_match: Optional[bool] = None,
    sort: Optional[str] = Query(default="submitted_at_asc"),
    page: Optional[int] = Query(default=1, ge=1),
    page_size: Optional[int] = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: TokenPayload = Depends(deps.get_current_user),
):
    """List venues for admin review."""
    _require_admin(current_user)
    return crud_venue_obj.get_admin_venues(
        db,
        status=status,
        domain_match=domain_match,
        sort=sort or "submitted_at_asc",
        page=page or 1,
        page_size=page_size or 20,
    )


@router.post("/admin/venues/{venueId}/approve", response_model=VenueAdminApproveResponse)
def approve_venue(
    venueId: str,
    db: Session = Depends(get_db),
    current_user: TokenPayload = Depends(deps.get_current_user),
):
    """Approve a venue listing."""
    _require_admin(current_user)
    try:
        venue = crud_venue_obj.approve(db, venue_id=venueId)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    if not venue:
        raise HTTPException(status_code=404, detail="Venue not found")
    # H-14: Notify venue owner
    if venue.email:
        try:
            from app.core.email import send_venue_approved_email
            send_venue_approved_email(to_email=venue.email, venue_name=venue.name)
        except Exception:
            pass  # best-effort
    return VenueAdminApproveResponse(
        id=venue.id,
        status=venue.status,
        verified=venue.verified,
        approved_at=venue.approved_at,
    )


@router.post("/admin/venues/{venueId}/reject", response_model=VenueAdminRejectResponse)
def reject_venue(
    venueId: str,
    body: AdminRejectRequest,
    db: Session = Depends(get_db),
    current_user: TokenPayload = Depends(deps.get_current_user),
):
    """Reject a venue listing."""
    _require_admin(current_user)
    try:
        venue = crud_venue_obj.reject(db, venue_id=venueId, reason=body.reason)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    if not venue:
        raise HTTPException(status_code=404, detail="Venue not found")
    # H-14: Notify venue owner
    if venue.email:
        try:
            from app.core.email import send_venue_rejected_email
            send_venue_rejected_email(
                to_email=venue.email, venue_name=venue.name, reason=body.reason,
            )
        except Exception:
            pass  # best-effort
    return VenueAdminRejectResponse(
        id=venue.id,
        status=venue.status,
        rejection_reason=venue.rejection_reason,
    )


@router.post("/admin/venues/{venueId}/suspend", response_model=AdminVenueSuspendResponse)
def suspend_venue(
    venueId: str,
    body: AdminSuspendRequest,
    db: Session = Depends(get_db),
    current_user: TokenPayload = Depends(deps.get_current_user),
):
    """Suspend a venue (removes from public directory)."""
    _require_admin(current_user)
    try:
        venue = crud_venue_obj.suspend(db, venue_id=venueId, reason=body.reason)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    if not venue:
        raise HTTPException(status_code=404, detail="Venue not found")
    # H-14: Notify venue owner
    if venue.email:
        try:
            from app.core.email import send_venue_suspended_email
            send_venue_suspended_email(
                to_email=venue.email, venue_name=venue.name, reason=body.reason,
            )
        except Exception:
            pass  # best-effort
    return AdminVenueSuspendResponse(id=venue.id, status=venue.status)


@router.post("/admin/venues/{venueId}/request-documents")
def request_documents(
    venueId: str,
    body: AdminRequestDocumentsRequest,
    db: Session = Depends(get_db),
    current_user: TokenPayload = Depends(deps.get_current_user),
):
    """Send a request for additional documents."""
    _require_admin(current_user)
    venue = crud_venue_obj.get(db, id=venueId)
    if not venue:
        raise HTTPException(status_code=404, detail="Venue not found")

    if not venue.email:
        raise HTTPException(
            status_code=422,
            detail="Venue has no contact email — cannot send document request",
        )

    from app.core.email import send_venue_document_request_email
    send_venue_document_request_email(
        to_email=venue.email,
        venue_name=venue.name,
        admin_message=body.message,
    )
    return {"message": "Document request sent", "venue_id": venueId}


# --- L-07: Admin single venue detail ---

@router.get("/admin/venues/{venueId}")
def admin_get_venue(
    venueId: str,
    db: Session = Depends(get_db),
    current_user: TokenPayload = Depends(deps.get_current_user),
):
    """Get a single venue with all relations (admin view)."""
    _require_admin(current_user)
    venue = crud_venue_obj.get_with_relations(db, id=venueId)
    if not venue:
        raise HTTPException(status_code=404, detail="Venue not found")
    return venue


# --- H-06: Update verification document status ---

@router.patch("/admin/venues/{venueId}/verification/{docId}")
def update_verification_status(
    venueId: str,
    docId: str,
    body: AdminVerificationStatusUpdate,
    db: Session = Depends(get_db),
    current_user: TokenPayload = Depends(deps.get_current_user),
):
    """Accept or reject a verification document."""
    _require_admin(current_user)
    venue = crud_venue_obj.get(db, id=venueId)
    if not venue:
        raise HTTPException(status_code=404, detail="Venue not found")
    doc = crud_verification.update_status(
        db, id=docId, status=body.status, admin_notes=body.admin_notes
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    if doc.venue_id != venueId:
        raise HTTPException(status_code=404, detail="Document not found")
    return {
        "id": doc.id,
        "venue_id": doc.venue_id,
        "status": doc.status,
        "admin_notes": doc.admin_notes,
    }


# --- Admin Amenity Management ---


@router.post(
    "/admin/amenity-categories",
    response_model=AmenityCategoryResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_amenity_category(
    body: AmenityCategoryCreate,
    db: Session = Depends(get_db),
    current_user: TokenPayload = Depends(deps.get_current_user),
):
    """Create a new amenity category."""
    _require_admin(current_user)
    return crud_amenity_obj.create_category(db, obj_in=body.model_dump())


@router.post(
    "/admin/amenities",
    response_model=AmenityResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_amenity(
    body: AmenityCreate,
    db: Session = Depends(get_db),
    current_user: TokenPayload = Depends(deps.get_current_user),
):
    """Create a new amenity within a category."""
    _require_admin(current_user)
    return crud_amenity_obj.create_amenity(db, obj_in=body.model_dump())


@router.patch("/admin/amenities/{amenityId}", response_model=AmenityResponse)
def update_amenity(
    amenityId: str,
    body: AmenityUpdate,
    db: Session = Depends(get_db),
    current_user: TokenPayload = Depends(deps.get_current_user),
):
    """Update an amenity."""
    _require_admin(current_user)
    amenity = crud_amenity_obj.get_amenity(db, id=amenityId)
    if not amenity:
        raise HTTPException(status_code=404, detail="Amenity not found")
    return crud_amenity_obj.update_amenity(
        db, db_obj=amenity, obj_in=body.model_dump(exclude_unset=True)
    )


@router.delete(
    "/admin/amenities/{amenityId}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_amenity(
    amenityId: str,
    db: Session = Depends(get_db),
    current_user: TokenPayload = Depends(deps.get_current_user),
):
    """Delete an amenity (only if no venues are using it)."""
    _require_admin(current_user)
    deleted = crud_amenity_obj.delete_amenity(db, id=amenityId)
    if not deleted:
        raise HTTPException(
            status_code=409,
            detail="Cannot delete amenity: it is in use by venues or not found",
        )
    from fastapi import Response
    return Response(status_code=status.HTTP_204_NO_CONTENT)
