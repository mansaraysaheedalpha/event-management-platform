# app/crud/crud_venue_response.py
from typing import Optional, List
from decimal import Decimal
from datetime import datetime, timezone
from sqlalchemy.orm import Session, joinedload

from app.models.venue_response import VenueResponse
from app.models.rfp_venue import RFPVenue
from app.models.rfp import RFP
from app.models.venue import Venue
from app.models.venue_space import VenueSpace
from app.schemas.venue_response import VenueResponseCreate


def get_by_rfp_venue(db: Session, rfp_venue_id: str) -> Optional[VenueResponse]:
    return (
        db.query(VenueResponse)
        .filter(VenueResponse.rfp_venue_id == rfp_venue_id)
        .first()
    )


def create(
    db: Session,
    *,
    rfp_venue: RFPVenue,
    rfp: RFP,
    data: VenueResponseCreate,
) -> VenueResponse:
    """
    Create a venue response. Auto-calculates total_estimated_cost and
    denormalizes space name/capacity from VenueSpace record.
    """
    obj_data = data.model_dump()

    # Denormalize space name and capacity
    proposed_space_name = "Custom Space"
    proposed_space_capacity = None
    if data.proposed_space_id:
        space = db.query(VenueSpace).filter(VenueSpace.id == data.proposed_space_id).first()
        if space:
            proposed_space_name = space.name
            proposed_space_capacity = space.capacity

    # Calculate total_estimated_cost
    total = Decimal("0")
    if data.space_rental_price:
        total += data.space_rental_price
    if data.catering_price_per_head:
        total += data.catering_price_per_head * rfp.attendance_max
    if data.av_equipment_fees:
        total += data.av_equipment_fees
    if data.setup_cleanup_fees:
        total += data.setup_cleanup_fees
    if data.other_fees:
        total += data.other_fees
    if data.extra_cost_amenities:
        for eca in data.extra_cost_amenities:
            total += Decimal(str(eca.price))

    # Convert extra_cost_amenities to dicts for JSON storage
    extra_cost_list = [eca.model_dump() for eca in data.extra_cost_amenities]

    db_obj = VenueResponse(
        rfp_venue_id=rfp_venue.id,
        availability=obj_data["availability"],
        proposed_space_id=obj_data.get("proposed_space_id"),
        proposed_space_name=proposed_space_name,
        proposed_space_capacity=proposed_space_capacity,
        currency=obj_data["currency"],
        space_rental_price=obj_data.get("space_rental_price"),
        catering_price_per_head=obj_data.get("catering_price_per_head"),
        av_equipment_fees=obj_data.get("av_equipment_fees"),
        setup_cleanup_fees=obj_data.get("setup_cleanup_fees"),
        other_fees=obj_data.get("other_fees"),
        other_fees_description=obj_data.get("other_fees_description"),
        included_amenity_ids=obj_data.get("included_amenity_ids", []),
        extra_cost_amenities=extra_cost_list,
        cancellation_policy=obj_data.get("cancellation_policy"),
        deposit_amount=obj_data.get("deposit_amount"),
        payment_schedule=obj_data.get("payment_schedule"),
        alternative_dates=obj_data.get("alternative_dates"),
        quote_valid_until=obj_data.get("quote_valid_until"),
        notes=obj_data.get("notes"),
        total_estimated_cost=total,
    )
    db.add(db_obj)

    # Update RFPVenue status
    rfp_venue.status = "responded"
    rfp_venue.responded_at = datetime.now(timezone.utc)

    # Check if this is the first response → transition RFP to collecting_responses
    if rfp.status == "sent":
        rfp.status = "collecting_responses"

    # Check if all venues have responded → transition to review
    from sqlalchemy import func as sa_func
    total_venues = (
        db.query(sa_func.count(RFPVenue.id))
        .filter(RFPVenue.rfp_id == rfp.id)
        .scalar()
    )
    responded_venues = (
        db.query(sa_func.count(RFPVenue.id))
        .filter(RFPVenue.rfp_id == rfp.id, RFPVenue.status == "responded")
        .scalar()
    )
    # +1 because the current rfp_venue status update hasn't been committed yet,
    # but we already set it to "responded" above, so the count includes it
    # Actually, since we set rfp_venue.status = "responded" above and haven't committed,
    # the query will pick it up in the same session. Let's check after flush.
    db.flush()

    responded_count = (
        db.query(sa_func.count(RFPVenue.id))
        .filter(RFPVenue.rfp_id == rfp.id, RFPVenue.status == "responded")
        .scalar()
    )
    if responded_count >= total_venues and rfp.status == "collecting_responses":
        rfp.status = "review"

    db.commit()
    db.refresh(db_obj)
    return db_obj


def get_comparison_data(db: Session, *, rfp: RFP) -> List[dict]:
    """Get all venue responses for comparison dashboard."""
    rfp_venues = (
        db.query(RFPVenue)
        .options(
            joinedload(RFPVenue.venue),
            joinedload(RFPVenue.response),
        )
        .filter(RFPVenue.rfp_id == rfp.id, RFPVenue.status == "responded")
        .all()
    )

    result = []
    for rv in rfp_venues:
        if not rv.response:
            continue

        resp = rv.response
        venue = rv.venue

        # Calculate response time in hours
        response_time_hours = 0.0
        if rfp.sent_at and rv.responded_at:
            delta = rv.responded_at - rfp.sent_at
            response_time_hours = round(delta.total_seconds() / 3600, 1)

        result.append({
            "rfv_id": rv.id,
            "venue_id": rv.venue_id,
            "venue_name": venue.name if venue else "Unknown",
            "venue_verified": venue.verified if venue else False,
            "venue_slug": venue.slug if venue else None,
            "status": rv.status,
            "response": resp,
            "amenity_match_pct": rv.amenity_match_pct or 0.0,
            "response_time_hours": response_time_hours,
        })

    return result
