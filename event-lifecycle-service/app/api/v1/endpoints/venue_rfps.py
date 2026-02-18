# app/api/v1/endpoints/venue_rfps.py
"""Venue owner RFP endpoints — inbox, detail, respond."""
import math
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session, joinedload

from app.api import deps
from app.db.session import get_db
from app.crud import crud_rfp_venue, crud_venue_response
from app.models.venue import Venue
from app.models.rfp import RFP
from app.models.rfp_venue import RFPVenue
from app.models.venue_space import VenueSpace
from app.models.amenity import Amenity
from app.models.amenity_category import AmenityCategory
from app.schemas.venue_response import VenueResponseCreate
from app.schemas.token import TokenPayload
from datetime import datetime, timezone

router = APIRouter(prefix="/venues/{venueId}/rfps", tags=["Venue RFPs"])


def _verify_venue_ownership(db: Session, venue_id: str, current_user: TokenPayload) -> Venue:
    """Verify the current user's org owns this venue."""
    venue = db.query(Venue).filter(Venue.id == venue_id).first()
    if not venue:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Venue not found")
    if venue.organization_id != current_user.org_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")
    return venue


@router.get("")
def venue_rfp_inbox(
    venueId: str,
    status_filter: Optional[str] = Query(default=None, alias="status"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=50),
    db: Session = Depends(get_db),
    current_user: TokenPayload = Depends(deps.get_current_user),
):
    """RFP inbox — list all RFPs received by this venue."""
    _verify_venue_ownership(db, venueId, current_user)

    query = (
        db.query(RFPVenue)
        .options(joinedload(RFPVenue.rfp))
        .filter(RFPVenue.venue_id == venueId)
    )

    if status_filter:
        query = query.filter(RFPVenue.status == status_filter)

    total_count = query.count()
    total_pages = math.ceil(total_count / page_size) if page_size > 0 else 0
    offset = (page - 1) * page_size

    rfp_venues = (
        query.order_by(RFPVenue.created_at.desc())
        .offset(offset)
        .limit(page_size)
        .all()
    )

    items = []
    for rv in rfp_venues:
        rfp = rv.rfp
        if not rfp:
            continue

        # Format attendance range
        attendance_range = f"{rfp.attendance_min}-{rfp.attendance_max}"

        # Format preferred dates
        if rfp.preferred_dates_start and rfp.preferred_dates_end:
            preferred_dates = (
                f"{rfp.preferred_dates_start.strftime('%b %d')}-"
                f"{rfp.preferred_dates_end.strftime('%d, %Y')}"
            )
        elif rfp.preferred_dates_start:
            preferred_dates = rfp.preferred_dates_start.strftime("%b %d, %Y")
        else:
            preferred_dates = "Flexible"

        items.append({
            "rfv_id": rv.id,
            "rfp_id": rfp.id,
            "title": rfp.title,
            "event_type": rfp.event_type,
            "organizer_name": rfp.organization_id,  # resolved via cross-service call in GraphQL
            "attendance_range": attendance_range,
            "preferred_dates": preferred_dates,
            "status": rv.status,
            "response_deadline": rfp.response_deadline,
            "received_at": rv.notified_at or rv.created_at,
        })

    return {
        "rfps": items,
        "pagination": {
            "page": page,
            "page_size": page_size,
            "total_count": total_count,
            "total_pages": total_pages,
        },
    }


@router.get("/{rfpId}")
def venue_rfp_detail(
    venueId: str,
    rfpId: str,
    db: Session = Depends(get_db),
    current_user: TokenPayload = Depends(deps.get_current_user),
):
    """View RFP details. Side effect: marks as viewed on first access."""
    venue = _verify_venue_ownership(db, venueId, current_user)

    rfv = crud_rfp_venue.get_rfv_for_venue_rfp(db, venueId, rfpId)
    if not rfv:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="RFP not found for this venue.",
        )

    rfp = rfv.rfp

    # Side effect: mark as viewed on first access
    rfv = crud_rfp_venue.mark_viewed(db, rfv=rfv)

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

    # Get venue's own spaces for selection
    venue_spaces = (
        db.query(VenueSpace)
        .filter(VenueSpace.venue_id == venueId)
        .order_by(VenueSpace.sort_order)
        .all()
    )

    spaces_data = [
        {
            "id": s.id,
            "name": s.name,
            "capacity": s.capacity,
            "layout_options": s.layout_options or [],
        }
        for s in venue_spaces
    ]

    # Existing response
    existing_response = None
    if rfv.response:
        resp = rfv.response
        existing_response = {
            "id": resp.id,
            "rfp_venue_id": resp.rfp_venue_id,
            "availability": resp.availability,
            "proposed_space_id": resp.proposed_space_id,
            "proposed_space_name": resp.proposed_space_name,
            "proposed_space_capacity": resp.proposed_space_capacity,
            "currency": resp.currency,
            "space_rental_price": float(resp.space_rental_price) if resp.space_rental_price else None,
            "catering_price_per_head": float(resp.catering_price_per_head) if resp.catering_price_per_head else None,
            "av_equipment_fees": float(resp.av_equipment_fees) if resp.av_equipment_fees else None,
            "setup_cleanup_fees": float(resp.setup_cleanup_fees) if resp.setup_cleanup_fees else None,
            "other_fees": float(resp.other_fees) if resp.other_fees else None,
            "other_fees_description": resp.other_fees_description,
            "total_estimated_cost": float(resp.total_estimated_cost),
            "included_amenity_ids": resp.included_amenity_ids or [],
            "extra_cost_amenities": resp.extra_cost_amenities or [],
            "cancellation_policy": resp.cancellation_policy,
            "deposit_amount": float(resp.deposit_amount) if resp.deposit_amount else None,
            "payment_schedule": resp.payment_schedule,
            "alternative_dates": resp.alternative_dates,
            "quote_valid_until": resp.quote_valid_until,
            "notes": resp.notes,
            "created_at": resp.created_at,
            "updated_at": resp.updated_at,
        }

    return {
        "rfv_id": rfv.id,
        "rfp_id": rfp.id,
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
        "additional_notes": rfp.additional_notes,
        "response_deadline": rfp.response_deadline,
        "status": rfv.status,
        "venue_spaces": spaces_data,
        "existing_response": existing_response,
    }


@router.post("/{rfpId}/respond", status_code=status.HTTP_201_CREATED)
def submit_venue_response(
    venueId: str,
    rfpId: str,
    body: VenueResponseCreate,
    db: Session = Depends(get_db),
    current_user: TokenPayload = Depends(deps.get_current_user),
):
    """Submit a structured response to an RFP."""
    _verify_venue_ownership(db, venueId, current_user)

    rfv = crud_rfp_venue.get_rfv_for_venue_rfp(db, venueId, rfpId)
    if not rfv:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="RFP not found for this venue.",
        )

    rfp = rfv.rfp

    # Validate venue status
    if rfv.status not in ("received", "viewed"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot respond with venue status '{rfv.status}'. Already responded or declined.",
        )

    # Validate deadline not passed
    if rfp.response_deadline <= datetime.now(timezone.utc):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Response deadline has passed.",
        )

    # Validate no existing response
    existing = crud_venue_response.get_by_rfp_venue(db, rfv.id)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A response has already been submitted for this RFP.",
        )

    response = crud_venue_response.create(db, rfp_venue=rfv, rfp=rfp, data=body)

    # Record availability signal
    try:
        from app.crud import crud_venue_availability

        signal_type_map = {
            "confirmed": "confirmed",
            "tentative": "tentative",
            "unavailable": "unavailable",
        }

        crud_venue_availability.record_signal(
            db=db,
            venue_id=rfv.venue_id,
            signal_type=signal_type_map[response.availability],
            source_rfp_id=rfp.id,
            source_rfp_venue_id=rfv.id,
            signal_date=rfp.preferred_dates_start,
            metadata={"attendance": rfp.attendance_max, "event_type": rfp.event_type},
        )
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Failed to record availability signal: {e}")
        # Don't fail the response submission

    # Notify organizer
    try:
        from app.utils.rfp_notifications import dispatch_venue_responded_notification
        dispatch_venue_responded_notification(db, rfv, rfp)
    except Exception:
        pass

    return {
        "id": response.id,
        "rfp_venue_id": response.rfp_venue_id,
        "availability": response.availability,
        "proposed_space_id": response.proposed_space_id,
        "proposed_space_name": response.proposed_space_name,
        "proposed_space_capacity": response.proposed_space_capacity,
        "currency": response.currency,
        "space_rental_price": float(response.space_rental_price) if response.space_rental_price else None,
        "catering_price_per_head": float(response.catering_price_per_head) if response.catering_price_per_head else None,
        "av_equipment_fees": float(response.av_equipment_fees) if response.av_equipment_fees else None,
        "setup_cleanup_fees": float(response.setup_cleanup_fees) if response.setup_cleanup_fees else None,
        "other_fees": float(response.other_fees) if response.other_fees else None,
        "other_fees_description": response.other_fees_description,
        "total_estimated_cost": float(response.total_estimated_cost),
        "included_amenity_ids": response.included_amenity_ids or [],
        "extra_cost_amenities": response.extra_cost_amenities or [],
        "cancellation_policy": response.cancellation_policy,
        "deposit_amount": float(response.deposit_amount) if response.deposit_amount else None,
        "payment_schedule": response.payment_schedule,
        "alternative_dates": response.alternative_dates,
        "quote_valid_until": response.quote_valid_until,
        "notes": response.notes,
        "created_at": response.created_at,
        "updated_at": response.updated_at,
    }
