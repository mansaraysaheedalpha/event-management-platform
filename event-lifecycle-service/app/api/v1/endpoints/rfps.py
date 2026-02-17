# app/api/v1/endpoints/rfps.py
"""Organizer RFP management + venue decision endpoints."""
import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, Response, Query
from sqlalchemy.orm import Session

from app.api import deps
from app.db.session import get_db
from app.crud import crud_rfp, crud_rfp_venue, crud_venue_response
from app.schemas.rfp import (
    RFPCreate,
    RFPUpdate,
    RFPResponse,
    RFPListResult,
    ExtendDeadlineRequest,
    CloseRFPRequest,
    SendRFPResponse,
)
from app.schemas.rfp_venue import (
    AddVenuesRequest,
    AddVenuesResponse,
    PreSendSummary,
    DeclineVenueRequest,
    RFPVenueResponse,
)
from app.schemas.venue_response import ComparisonDashboard, ComparisonBadges
from app.schemas.token import TokenPayload
from app.models.amenity import Amenity
from app.models.amenity_category import AmenityCategory
from app.models.venue_photo import VenuePhoto
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/organizations/{orgId}/rfps", tags=["RFPs"])


# ── Helpers ───────────────────────────────────────────────────────────

def _check_org_auth(current_user: TokenPayload, orgId: str):
    if current_user.org_id != orgId:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")


def _get_rfp_or_404(db: Session, rfp_id: str, org_id: str):
    rfp = crud_rfp.get(db, rfp_id)
    if not rfp or rfp.organization_id != org_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="RFP not found")
    return rfp


def _get_rfp_simple_or_404(db: Session, rfp_id: str, org_id: str):
    rfp = crud_rfp.get_simple(db, rfp_id)
    if not rfp or rfp.organization_id != org_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="RFP not found")
    return rfp


def _build_rfp_response(db: Session, rfp) -> dict:
    """Build the full RFP response dict with resolved amenities and venue details."""
    # Resolve required amenities
    required_amenities = []
    if rfp.required_amenity_ids:
        amenities = (
            db.query(Amenity.id, Amenity.name, AmenityCategory.name.label("category"))
            .join(AmenityCategory, AmenityCategory.id == Amenity.category_id)
            .filter(Amenity.id.in_(rfp.required_amenity_ids))
            .all()
        )
        required_amenities = [
            {"id": a.id, "name": a.name, "category": a.category}
            for a in amenities
        ]

    # Build venue list
    venues_list = []
    for rv in (rfp.venues or []):
        venue = rv.venue
        # Get cover photo
        cover_photo_url = None
        if venue:
            cover = (
                db.query(VenuePhoto.url)
                .filter(VenuePhoto.venue_id == venue.id, VenuePhoto.is_cover == True)
                .first()
            )
            if cover:
                cover_photo_url = cover.url

        venues_list.append({
            "id": rv.id,
            "venue_id": rv.venue_id,
            "venue_name": venue.name if venue else "Unknown",
            "venue_slug": venue.slug if venue else None,
            "venue_city": venue.city if venue else None,
            "venue_country": venue.country if venue else None,
            "venue_verified": venue.verified if venue else False,
            "venue_cover_photo_url": cover_photo_url,
            "status": rv.status,
            "capacity_fit": rv.capacity_fit,
            "amenity_match_pct": rv.amenity_match_pct,
            "notified_at": rv.notified_at,
            "viewed_at": rv.viewed_at,
            "responded_at": rv.responded_at,
            "has_response": rv.response is not None,
        })

    return {
        "id": rfp.id,
        "organization_id": rfp.organization_id,
        "title": rfp.title,
        "event_type": rfp.event_type,
        "attendance_min": rfp.attendance_min,
        "attendance_max": rfp.attendance_max,
        "preferred_dates_start": rfp.preferred_dates_start,
        "preferred_dates_end": rfp.preferred_dates_end,
        "dates_flexible": rfp.dates_flexible,
        "duration": rfp.duration,
        "space_requirements": rfp.space_requirements or [],
        "required_amenities": required_amenities,
        "catering_needs": rfp.catering_needs,
        "budget_min": float(rfp.budget_min) if rfp.budget_min else None,
        "budget_max": float(rfp.budget_max) if rfp.budget_max else None,
        "budget_currency": rfp.budget_currency,
        "preferred_currency": rfp.preferred_currency,
        "additional_notes": rfp.additional_notes,
        "response_deadline": rfp.response_deadline,
        "linked_event_id": rfp.linked_event_id,
        "organizer_email": rfp.organizer_email,
        "status": rfp.status,
        "sent_at": rfp.sent_at,
        "venues": venues_list,
        "created_at": rfp.created_at,
        "updated_at": rfp.updated_at,
    }


# ── CRUD Endpoints (Section 2.1) ─────────────────────────────────────

@router.post("", status_code=status.HTTP_201_CREATED)
def create_rfp(
    orgId: str,
    rfp_in: RFPCreate,
    db: Session = Depends(get_db),
    current_user: TokenPayload = Depends(deps.get_current_user),
):
    """Create a new draft RFP. Max 5 active RFPs per organizer."""
    _check_org_auth(current_user, orgId)

    active_count = crud_rfp.count_active_rfps(db, orgId)
    if active_count >= 5:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Maximum 5 active RFPs per organizer. Close or complete existing RFPs first.",
        )

    rfp = crud_rfp.create(db, org_id=orgId, data=rfp_in)

    # Audit log
    from app.crud import crud_rfp_audit_log
    crud_rfp_audit_log.create_audit_entry(
        db=db,
        rfp_id=rfp.id,
        user_id=current_user.sub,
        action="create",
        new_state="draft",
        metadata={"title": rfp.title},
    )

    rfp = crud_rfp.get(db, rfp.id)  # reload with relations
    return _build_rfp_response(db, rfp)


@router.get("")
def list_rfps(
    orgId: str,
    status_filter: Optional[str] = Query(default=None, alias="status"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=50),
    db: Session = Depends(get_db),
    current_user: TokenPayload = Depends(deps.get_current_user),
):
    """List organizer's RFPs with pagination."""
    _check_org_auth(current_user, orgId)
    return crud_rfp.list_by_org(db, orgId, status=status_filter, page=page, page_size=page_size)


@router.get("/{rfpId}")
def get_rfp(
    orgId: str,
    rfpId: str,
    db: Session = Depends(get_db),
    current_user: TokenPayload = Depends(deps.get_current_user),
):
    """Get RFP detail with all venue statuses."""
    _check_org_auth(current_user, orgId)
    rfp = _get_rfp_or_404(db, rfpId, orgId)
    return _build_rfp_response(db, rfp)


@router.patch("/{rfpId}")
def update_rfp(
    orgId: str,
    rfpId: str,
    rfp_in: RFPUpdate,
    db: Session = Depends(get_db),
    current_user: TokenPayload = Depends(deps.get_current_user),
):
    """Update a draft RFP. Only allowed when status = draft."""
    _check_org_auth(current_user, orgId)
    rfp = _get_rfp_simple_or_404(db, rfpId, orgId)

    if rfp.status != "draft":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Cannot update RFP with status '{rfp.status}'. Must be 'draft'.",
        )

    rfp = crud_rfp.update(db, rfp=rfp, data=rfp_in)
    rfp = crud_rfp.get(db, rfp.id)
    return _build_rfp_response(db, rfp)


@router.delete("/{rfpId}", status_code=status.HTTP_204_NO_CONTENT)
def delete_rfp(
    orgId: str,
    rfpId: str,
    db: Session = Depends(get_db),
    current_user: TokenPayload = Depends(deps.get_current_user),
):
    """Delete a draft RFP. Only allowed when status = draft."""
    _check_org_auth(current_user, orgId)
    rfp = _get_rfp_simple_or_404(db, rfpId, orgId)

    if rfp.status != "draft":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Cannot delete RFP with status '{rfp.status}'. Must be 'draft'.",
        )

    crud_rfp.delete(db, rfp=rfp)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ── Venue Selection (Section 2.2) ────────────────────────────────────

@router.post("/{rfpId}/venues", status_code=status.HTTP_201_CREATED)
def add_venues_to_rfp(
    orgId: str,
    rfpId: str,
    body: AddVenuesRequest,
    db: Session = Depends(get_db),
    current_user: TokenPayload = Depends(deps.get_current_user),
):
    """Add venues to a draft RFP. Max 10 venues per RFP."""
    _check_org_auth(current_user, orgId)
    rfp = _get_rfp_or_404(db, rfpId, orgId)

    if rfp.status != "draft":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Can only add venues to a draft RFP.",
        )

    current_count = crud_rfp_venue.count_venues_for_rfp(db, rfpId)
    if current_count + len(body.venue_ids) > 10:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Maximum 10 venues per RFP. Currently {current_count}, trying to add {len(body.venue_ids)}.",
        )

    result = crud_rfp_venue.add_venues(db, rfp=rfp, venue_ids=body.venue_ids)
    return result


@router.delete("/{rfpId}/venues/{venueId}", status_code=status.HTTP_204_NO_CONTENT)
def remove_venue_from_rfp(
    orgId: str,
    rfpId: str,
    venueId: str,
    db: Session = Depends(get_db),
    current_user: TokenPayload = Depends(deps.get_current_user),
):
    """Remove a venue from a draft RFP."""
    _check_org_auth(current_user, orgId)
    rfp = _get_rfp_simple_or_404(db, rfpId, orgId)

    if rfp.status != "draft":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Can only remove venues from a draft RFP.",
        )

    removed = crud_rfp_venue.remove_venue(db, rfp_id=rfpId, venue_id=venueId)
    if not removed:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Venue not found in this RFP.",
        )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{rfpId}/pre-send-summary")
def get_pre_send_summary(
    orgId: str,
    rfpId: str,
    db: Session = Depends(get_db),
    current_user: TokenPayload = Depends(deps.get_current_user),
):
    """Get pre-send fit indicators for all selected venues."""
    _check_org_auth(current_user, orgId)
    rfp = _get_rfp_or_404(db, rfpId, orgId)

    venues = crud_rfp_venue.get_pre_send_summary(db, rfp=rfp)
    return {
        "rfp_id": rfp.id,
        "venue_count": len(venues),
        "venues": venues,
    }


# ── RFP Actions (Section 2.3) ────────────────────────────────────────

@router.post("/{rfpId}/send")
def send_rfp(
    orgId: str,
    rfpId: str,
    db: Session = Depends(get_db),
    current_user: TokenPayload = Depends(deps.get_current_user),
):
    """Send RFP to all selected venues. Triggers notifications."""
    _check_org_auth(current_user, orgId)
    rfp = _get_rfp_or_404(db, rfpId, orgId)

    if rfp.status != "draft":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Cannot send RFP with status '{rfp.status}'. Must be 'draft'.",
        )

    if not rfp.venues:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="RFP must have at least 1 venue selected before sending.",
        )

    if rfp.response_deadline <= datetime.now(timezone.utc):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Response deadline must be in the future.",
        )

    old_status = rfp.status
    rfp = crud_rfp.send(db, rfp=rfp)

    # Audit log
    from app.crud import crud_rfp_audit_log
    crud_rfp_audit_log.create_audit_entry(
        db=db,
        rfp_id=rfp.id,
        user_id=current_user.sub,
        action="send",
        old_state=old_status,
        new_state=rfp.status,
        metadata={"venues_count": len(rfp.venues)},
    )

    # Trigger notifications asynchronously (best-effort)
    try:
        from app.utils.rfp_notifications import dispatch_rfp_send_notifications
        dispatch_rfp_send_notifications(db, rfp)
    except Exception:
        pass  # Notification failures don't block the send

    return {
        "id": rfp.id,
        "status": rfp.status,
        "sent_at": rfp.sent_at,
        "venues_notified": len(rfp.venues),
    }


@router.post("/{rfpId}/extend-deadline")
def extend_rfp_deadline(
    orgId: str,
    rfpId: str,
    body: ExtendDeadlineRequest,
    db: Session = Depends(get_db),
    current_user: TokenPayload = Depends(deps.get_current_user),
):
    """Extend the response deadline."""
    _check_org_auth(current_user, orgId)
    rfp = _get_rfp_simple_or_404(db, rfpId, orgId)

    if rfp.status not in ("sent", "collecting_responses"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Cannot extend deadline for RFP with status '{rfp.status}'.",
        )

    if body.new_deadline <= rfp.response_deadline:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="New deadline must be after the current deadline.",
        )

    old_deadline = rfp.response_deadline
    rfp = crud_rfp.extend_deadline(db, rfp=rfp, new_deadline=body.new_deadline)

    # Audit log
    from app.crud import crud_rfp_audit_log
    crud_rfp_audit_log.create_audit_entry(
        db=db,
        rfp_id=rfp.id,
        user_id=current_user.sub,
        action="extend_deadline",
        metadata={
            "deadline_old": old_deadline.isoformat(),
            "deadline_new": rfp.response_deadline.isoformat(),
        },
    )

    # Notify non-responding venues
    try:
        from app.utils.rfp_notifications import dispatch_deadline_extended_notifications
        dispatch_deadline_extended_notifications(db, rfp)
    except Exception:
        pass

    rfp = crud_rfp.get(db, rfp.id)
    return _build_rfp_response(db, rfp)


@router.post("/{rfpId}/close")
def close_rfp(
    orgId: str,
    rfpId: str,
    body: CloseRFPRequest = None,
    db: Session = Depends(get_db),
    current_user: TokenPayload = Depends(deps.get_current_user),
):
    """Close RFP without awarding."""
    _check_org_auth(current_user, orgId)
    rfp = _get_rfp_simple_or_404(db, rfpId, orgId)

    if rfp.status not in ("sent", "collecting_responses", "review"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Cannot close RFP with status '{rfp.status}'.",
        )

    old_status = rfp.status
    rfp = crud_rfp.close(db, rfp=rfp)

    # Audit log
    from app.crud import crud_rfp_audit_log
    crud_rfp_audit_log.create_audit_entry(
        db=db,
        rfp_id=rfp.id,
        user_id=current_user.sub,
        action="close",
        old_state=old_status,
        new_state=rfp.status,
        metadata={"reason": body.reason if body else None},
    )

    rfp = crud_rfp.get(db, rfp.id)
    return _build_rfp_response(db, rfp)


@router.post("/{rfpId}/duplicate", status_code=status.HTTP_201_CREATED)
def duplicate_rfp(
    orgId: str,
    rfpId: str,
    db: Session = Depends(get_db),
    current_user: TokenPayload = Depends(deps.get_current_user),
):
    """Clone an RFP to a new draft. Works from any state."""
    _check_org_auth(current_user, orgId)
    rfp = _get_rfp_simple_or_404(db, rfpId, orgId)

    new_rfp = crud_rfp.duplicate(db, rfp=rfp)

    # Audit log for the new RFP
    from app.crud import crud_rfp_audit_log
    crud_rfp_audit_log.create_audit_entry(
        db=db,
        rfp_id=new_rfp.id,
        user_id=current_user.sub,
        action="duplicate",
        new_state="draft",
        metadata={"source_rfp_id": rfpId, "title": new_rfp.title},
    )

    new_rfp = crud_rfp.get(db, new_rfp.id)
    return _build_rfp_response(db, new_rfp)


# ── Venue Decision Actions (Section 2.4) ─────────────────────────────

def _get_rfv_or_404(db: Session, rfpId: str, rfvId: str):
    rfv = crud_rfp_venue.get(db, rfvId)
    if not rfv or rfv.rfp_id != rfpId:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="RFP-Venue junction not found.",
        )
    return rfv


@router.post("/{rfpId}/venues/{rfvId}/shortlist")
def shortlist_venue(
    orgId: str,
    rfpId: str,
    rfvId: str,
    db: Session = Depends(get_db),
    current_user: TokenPayload = Depends(deps.get_current_user),
):
    """Shortlist a venue. Allowed when venue status is 'responded'."""
    _check_org_auth(current_user, orgId)
    _get_rfp_simple_or_404(db, rfpId, orgId)  # verify org owns RFP
    rfv = _get_rfv_or_404(db, rfpId, rfvId)

    if rfv.status != "responded":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Cannot shortlist venue with status '{rfv.status}'. Must be 'responded'.",
        )

    old_status = rfv.status
    rfv = crud_rfp_venue.shortlist(db, rfv=rfv)

    # Audit log
    from app.crud import crud_rfp_audit_log
    crud_rfp_audit_log.create_audit_entry(
        db=db,
        rfp_id=rfpId,
        rfp_venue_id=rfvId,
        user_id=current_user.sub,
        action="shortlist",
        old_state=old_status,
        new_state=rfv.status,
        metadata={"venue_id": rfv.venue_id},
    )

    return {
        "id": rfv.id,
        "rfp_id": rfv.rfp_id,
        "venue_id": rfv.venue_id,
        "status": rfv.status,
        "notified_at": rfv.notified_at,
        "viewed_at": rfv.viewed_at,
        "responded_at": rfv.responded_at,
        "capacity_fit": rfv.capacity_fit,
        "amenity_match_pct": rfv.amenity_match_pct,
        "created_at": rfv.created_at,
        "updated_at": rfv.updated_at,
    }


@router.post("/{rfpId}/venues/{rfvId}/award")
def award_venue(
    orgId: str,
    rfpId: str,
    rfvId: str,
    db: Session = Depends(get_db),
    current_user: TokenPayload = Depends(deps.get_current_user),
):
    """Award the RFP to a venue. Only one venue can be awarded per RFP."""
    _check_org_auth(current_user, orgId)
    rfp = _get_rfp_simple_or_404(db, rfpId, orgId)
    rfv = _get_rfv_or_404(db, rfpId, rfvId)

    if rfv.status not in ("responded", "shortlisted"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Cannot award venue with status '{rfv.status}'. Must be 'responded' or 'shortlisted'.",
        )

    # Check no other venue already awarded
    from app.models.rfp_venue import RFPVenue
    already_awarded = (
        db.query(RFPVenue)
        .filter(RFPVenue.rfp_id == rfpId, RFPVenue.status == "awarded")
        .first()
    )
    if already_awarded:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Another venue has already been awarded for this RFP.",
        )

    old_status = rfv.status
    rfv = crud_rfp_venue.award(db, rfv=rfv, rfp=rfp)

    # Audit log
    from app.crud import crud_rfp_audit_log
    crud_rfp_audit_log.create_audit_entry(
        db=db,
        rfp_id=rfpId,
        rfp_venue_id=rfvId,
        user_id=current_user.sub,
        action="award",
        old_state=old_status,
        new_state=rfv.status,
        metadata={"venue_id": rfv.venue_id},
    )

    # Notify venue of acceptance
    try:
        from app.utils.rfp_notifications import dispatch_proposal_accepted_notification
        dispatch_proposal_accepted_notification(db, rfv)
    except Exception:
        pass

    return {
        "id": rfv.id,
        "rfp_id": rfv.rfp_id,
        "venue_id": rfv.venue_id,
        "status": rfv.status,
        "notified_at": rfv.notified_at,
        "viewed_at": rfv.viewed_at,
        "responded_at": rfv.responded_at,
        "capacity_fit": rfv.capacity_fit,
        "amenity_match_pct": rfv.amenity_match_pct,
        "created_at": rfv.created_at,
        "updated_at": rfv.updated_at,
    }


@router.post("/{rfpId}/venues/{rfvId}/decline")
def decline_venue(
    orgId: str,
    rfpId: str,
    rfvId: str,
    body: DeclineVenueRequest = None,
    db: Session = Depends(get_db),
    current_user: TokenPayload = Depends(deps.get_current_user),
):
    """Decline a venue's proposal."""
    _check_org_auth(current_user, orgId)
    _get_rfp_simple_or_404(db, rfpId, orgId)
    rfv = _get_rfv_or_404(db, rfpId, rfvId)

    if rfv.status not in ("responded", "shortlisted"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Cannot decline venue with status '{rfv.status}'.",
        )

    old_status = rfv.status
    rfv = crud_rfp_venue.decline(db, rfv=rfv)

    # Audit log
    from app.crud import crud_rfp_audit_log
    crud_rfp_audit_log.create_audit_entry(
        db=db,
        rfp_id=rfpId,
        rfp_venue_id=rfvId,
        user_id=current_user.sub,
        action="decline",
        old_state=old_status,
        new_state=rfv.status,
        metadata={"venue_id": rfv.venue_id, "reason": body.reason if body else None},
    )

    # Notify venue of decline
    try:
        from app.utils.rfp_notifications import dispatch_proposal_declined_notification
        dispatch_proposal_declined_notification(db, rfv, reason=body.reason if body else None)
    except Exception:
        pass

    return {
        "id": rfv.id,
        "rfp_id": rfv.rfp_id,
        "venue_id": rfv.venue_id,
        "status": rfv.status,
        "notified_at": rfv.notified_at,
        "viewed_at": rfv.viewed_at,
        "responded_at": rfv.responded_at,
        "capacity_fit": rfv.capacity_fit,
        "amenity_match_pct": rfv.amenity_match_pct,
        "created_at": rfv.created_at,
        "updated_at": rfv.updated_at,
    }


# ── Comparison Dashboard (Section 2.5) ───────────────────────────────

@router.get("/{rfpId}/compare")
def get_comparison_dashboard(
    orgId: str,
    rfpId: str,
    db: Session = Depends(get_db),
    current_user: TokenPayload = Depends(deps.get_current_user),
):
    """Get structured comparison data for all venue responses."""
    _check_org_auth(current_user, orgId)
    rfp = _get_rfp_or_404(db, rfpId, orgId)

    raw_data = crud_venue_response.get_comparison_data(db, rfp=rfp)

    # Fetch exchange rates
    exchange_rate_data = None
    try:
        from app.utils.exchange_rates import get_exchange_rates_sync
        exchange_rate_data = get_exchange_rates_sync(rfp.preferred_currency)
    except Exception:
        pass

    required_amenity_count = len(rfp.required_amenity_ids) if rfp.required_amenity_ids else 0

    venues = []
    best_value_rfv = None
    best_value_cost = None
    best_match_rfv = None
    best_match_pct = -1.0

    for item in raw_data:
        resp = item["response"]
        total_cost = float(resp.total_estimated_cost)

        # Convert to preferred currency
        total_in_preferred = total_cost
        can_compare = True  # Track if currency conversion succeeded

        if exchange_rate_data and resp.currency != rfp.preferred_currency:
            rates = exchange_rate_data.get("rates", {})
            from_rate = rates.get(resp.currency)
            if from_rate and from_rate > 0:
                # rates are relative to base (preferred_currency)
                # To convert FROM resp.currency TO preferred_currency:
                # Formula: amount_in_preferred = amount / rate_of_resp_currency
                # Verified: 1 USD = 129 KES, so 100,000 KES / 129 = 775 USD ✓
                total_in_preferred = total_cost / from_rate

                # Log conversions for first 2 weeks (remove after 2025-03-03)
                logger.info(
                    f"[CURRENCY_CONVERSION] RFP {rfp.id}: "
                    f"{total_cost} {resp.currency} → {total_in_preferred:.2f} {rfp.preferred_currency} "
                    f"(rate: 1 {rfp.preferred_currency} = {from_rate} {resp.currency})"
                )
            else:
                # Conversion failed - cannot compare this venue's price
                can_compare = False
        # If same currency, can always compare

        # Track badges
        amenity_pct = item["amenity_match_pct"]

        # Only include in best value if currency conversion succeeded
        if can_compare and (best_value_cost is None or total_in_preferred < best_value_cost):
            best_value_cost = total_in_preferred
            best_value_rfv = item["rfv_id"]

        if amenity_pct > best_match_pct:
            best_match_pct = amenity_pct
            best_match_rfv = item["rfv_id"]

        badges = []

        venues.append({
            "rfv_id": item["rfv_id"],
            "venue_id": item["venue_id"],
            "venue_name": item["venue_name"],
            "venue_verified": item["venue_verified"],
            "venue_slug": item["venue_slug"],
            "status": item["status"],
            "response": {
                "id": resp.id,
                "availability": resp.availability,
                "proposed_space_name": resp.proposed_space_name,
                "proposed_space_capacity": resp.proposed_space_capacity,
                "currency": resp.currency,
                "space_rental_price": float(resp.space_rental_price) if resp.space_rental_price else None,
                "catering_price_per_head": float(resp.catering_price_per_head) if resp.catering_price_per_head else None,
                "av_equipment_fees": float(resp.av_equipment_fees) if resp.av_equipment_fees else None,
                "setup_cleanup_fees": float(resp.setup_cleanup_fees) if resp.setup_cleanup_fees else None,
                "other_fees": float(resp.other_fees) if resp.other_fees else None,
                "total_estimated_cost": total_cost,
                "total_in_preferred_currency": round(total_in_preferred, 2),
                "included_amenity_ids": resp.included_amenity_ids or [],
                "extra_cost_amenities": resp.extra_cost_amenities or [],
                "deposit_amount": float(resp.deposit_amount) if resp.deposit_amount else None,
                "quote_valid_until": resp.quote_valid_until,
                "cancellation_policy": resp.cancellation_policy,
                "created_at": resp.created_at,
            },
            "amenity_match_pct": amenity_pct,
            "response_time_hours": item["response_time_hours"],
            "badges": badges,
        })

    # Assign badges
    for v in venues:
        if v["rfv_id"] == best_value_rfv:
            v["badges"].append("best_value")
        if v["rfv_id"] == best_match_rfv:
            v["badges"].append("best_match")

    return {
        "rfp_id": rfp.id,
        "preferred_currency": rfp.preferred_currency,
        "exchange_rates": exchange_rate_data,
        "required_amenity_count": required_amenity_count,
        "venues": venues,
        "badges": {
            "best_value": best_value_rfv,
            "best_match": best_match_rfv,
        },
    }


# ── Audit Trail ────────────────────────────────────────────────────────

@router.get("/{rfpId}/audit-log")
def get_rfp_audit_log(
    orgId: str,
    rfpId: str,
    db: Session = Depends(get_db),
    current_user: TokenPayload = Depends(deps.get_current_user),
):
    """Get audit trail for an RFP showing all state changes and actions."""
    _check_org_auth(current_user, orgId)
    _get_rfp_simple_or_404(db, rfpId, orgId)  # verify org owns RFP

    from app.crud import crud_rfp_audit_log

    entries = crud_rfp_audit_log.get_audit_log_for_rfp(db, rfpId, limit=100)

    return {
        "rfp_id": rfpId,
        "entries": [
            {
                "id": str(entry.id),
                "user_id": entry.user_id,
                "action": entry.action,
                "old_state": entry.old_state,
                "new_state": entry.new_state,
                "metadata": entry.metadata,
                "rfp_venue_id": entry.rfp_venue_id,
                "created_at": entry.created_at.isoformat(),
            }
            for entry in entries
        ],
    }
