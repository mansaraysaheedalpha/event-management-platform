# app/crud/crud_rfp_venue.py
import logging
from typing import Optional, List
from datetime import datetime, timezone
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func

from app.models.rfp import RFP
from app.models.rfp_venue import RFPVenue
from app.models.venue import Venue
from app.models.venue_space import VenueSpace
from app.models.venue_space_pricing import VenueSpacePricing
from app.models.venue_amenity import VenueAmenity
from app.models.amenity import Amenity
from app.models.venue_photo import VenuePhoto

logger = logging.getLogger(__name__)

# Valid state transitions for RFPVenue
VALID_VENUE_TRANSITIONS = {
    "received": {"viewed", "no_response"},
    "viewed": {"responded", "no_response"},
    "responded": {"shortlisted", "awarded", "declined"},
    "shortlisted": {"awarded", "declined"},
    "awarded": set(),  # Terminal state
    "declined": set(),  # Terminal state
    "no_response": set(),  # Terminal state
}


def validate_transition(old_status: str, new_status: str) -> bool:
    """
    Validate that a status transition is allowed.
    Returns True if valid, False otherwise.
    """
    if old_status not in VALID_VENUE_TRANSITIONS:
        logger.warning(f"Unknown status: {old_status}")
        return False

    if new_status not in VALID_VENUE_TRANSITIONS[old_status]:
        logger.warning(f"Invalid transition: {old_status} → {new_status}")
        return False

    return True


def transition_status(
    db: Session,
    rfv: RFPVenue,
    new_status: str,
    validate: bool = True,
) -> bool:
    """
    Validate and execute a venue status transition.
    Returns True on success, False if transition is invalid.
    """
    old_status = rfv.status

    if validate and not validate_transition(old_status, new_status):
        return False

    rfv.status = new_status

    # Update timestamps
    if new_status == "viewed" and not rfv.viewed_at:
        rfv.viewed_at = datetime.now(timezone.utc)
    elif new_status == "responded" and not rfv.responded_at:
        rfv.responded_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(rfv)
    return True


def get(db: Session, rfv_id: str) -> Optional[RFPVenue]:
    return (
        db.query(RFPVenue)
        .options(joinedload(RFPVenue.venue), joinedload(RFPVenue.response))
        .filter(RFPVenue.id == rfv_id)
        .first()
    )


def get_by_rfp_and_venue(db: Session, rfp_id: str, venue_id: str) -> Optional[RFPVenue]:
    return (
        db.query(RFPVenue)
        .filter(RFPVenue.rfp_id == rfp_id, RFPVenue.venue_id == venue_id)
        .first()
    )


def get_rfv_for_venue_rfp(db: Session, venue_id: str, rfp_id: str) -> Optional[RFPVenue]:
    """Get the RFPVenue junction for a specific venue receiving a specific RFP."""
    return (
        db.query(RFPVenue)
        .options(joinedload(RFPVenue.rfp), joinedload(RFPVenue.response))
        .filter(RFPVenue.venue_id == venue_id, RFPVenue.rfp_id == rfp_id)
        .first()
    )


def count_venues_for_rfp(db: Session, rfp_id: str) -> int:
    return (
        db.query(func.count(RFPVenue.id))
        .filter(RFPVenue.rfp_id == rfp_id)
        .scalar()
    )


def add_venues(
    db: Session,
    *,
    rfp: RFP,
    venue_ids: List[str],
) -> dict:
    """
    Add venues to an RFP. Computes fit indicators.
    Returns dict with 'added' (list) and 'skipped' (list).
    """
    existing_venue_ids = {
        rv.venue_id for rv in db.query(RFPVenue.venue_id).filter(RFPVenue.rfp_id == rfp.id).all()
    }

    # Load venue details for fit computation
    venues = db.query(Venue).filter(Venue.id.in_(venue_ids)).all()
    venue_map = {v.id: v for v in venues}

    added = []
    skipped = []

    for vid in venue_ids:
        if vid in existing_venue_ids:
            skipped.append(vid)
            continue

        venue = venue_map.get(vid)
        if not venue:
            skipped.append(vid)
            continue

        # Compute fit indicators
        cap_fit = compute_capacity_fit(venue.total_capacity, rfp.attendance_max)
        amenity_pct = compute_amenity_match(db, venue.id, rfp.required_amenity_ids or [])

        rfv = RFPVenue(
            rfp_id=rfp.id,
            venue_id=vid,
            status="received",
            capacity_fit=cap_fit,
            amenity_match_pct=amenity_pct,
        )
        db.add(rfv)
        db.flush()

        added.append({
            "id": rfv.id,
            "venue_id": vid,
            "venue_name": venue.name,
            "capacity_fit": cap_fit,
            "amenity_match_pct": amenity_pct,
            "status": "received",
        })

    db.commit()
    return {"added": added, "skipped": skipped}


def remove_venue(db: Session, *, rfp_id: str, venue_id: str) -> bool:
    rfv = get_by_rfp_and_venue(db, rfp_id, venue_id)
    if not rfv:
        return False
    db.delete(rfv)
    db.commit()
    return True


def mark_viewed(db: Session, *, rfv: RFPVenue) -> RFPVenue:
    """Mark RFP as viewed by venue owner. Only transitions from 'received'."""
    if rfv.status == "received":
        success = transition_status(db, rfv, "viewed", validate=True)
        if not success:
            logger.error(f"Failed to mark RFPVenue {rfv.id} as viewed")
    return rfv


def shortlist(db: Session, *, rfv: RFPVenue) -> RFPVenue:
    """Shortlist a venue. Only transitions from 'responded'."""
    success = transition_status(db, rfv, "shortlisted", validate=True)
    if not success:
        logger.error(f"Failed to shortlist RFPVenue {rfv.id}: invalid transition from {rfv.status}")
    return rfv


def award(db: Session, *, rfv: RFPVenue, rfp: RFP) -> RFPVenue:
    """Award RFP to a venue. Only transitions from 'responded' or 'shortlisted'."""
    success = transition_status(db, rfv, "awarded", validate=True)
    if not success:
        logger.error(f"Failed to award RFPVenue {rfv.id}: invalid transition from {rfv.status}")
        return rfv

    rfp.status = "awarded"
    db.commit()

    # Auto-decline all other responded/shortlisted venues
    other_venues = (
        db.query(RFPVenue)
        .filter(
            RFPVenue.rfp_id == rfp.id,
            RFPVenue.id != rfv.id,
            RFPVenue.status.in_(("responded", "shortlisted")),
        )
        .all()
    )
    for ov in other_venues:
        # Skip validation for auto-decline (administrative action)
        transition_status(db, ov, "declined", validate=False)

    return rfv


def decline(db: Session, *, rfv: RFPVenue) -> RFPVenue:
    """Decline a venue's response. Only transitions from 'responded' or 'shortlisted'."""
    success = transition_status(db, rfv, "declined", validate=True)
    if not success:
        logger.error(f"Failed to decline RFPVenue {rfv.id}: invalid transition from {rfv.status}")
    return rfv


def mark_no_response(db: Session, *, rfp_id: str) -> int:
    """
    Bulk mark all non-responded venues as 'no_response'. Returns count.
    Also records availability signals for each venue.
    """
    # Get the RFP for signal recording
    rfp = db.query(RFP).filter(RFP.id == rfp_id).first()

    # Get all venues to mark before update
    venues_to_mark = (
        db.query(RFPVenue)
        .filter(
            RFPVenue.rfp_id == rfp_id,
            RFPVenue.status.in_(("received", "viewed")),
        )
        .all()
    )

    # Update status
    count = (
        db.query(RFPVenue)
        .filter(
            RFPVenue.rfp_id == rfp_id,
            RFPVenue.status.in_(("received", "viewed")),
        )
        .update({"status": "no_response"}, synchronize_session="fetch")
    )
    db.commit()

    # Record signals for each no-response venue
    if rfp:
        try:
            from app.crud import crud_venue_availability

            for rfv in venues_to_mark:
                try:
                    crud_venue_availability.record_signal(
                        db=db,
                        venue_id=rfv.venue_id,
                        signal_type="no_response",
                        source_rfp_id=rfp.id,
                        source_rfp_venue_id=rfv.id,
                        signal_date=rfp.preferred_dates_start,
                    )
                except Exception as e:
                    logger.error(f"Failed to record no_response signal for venue {rfv.venue_id}: {e}")
        except Exception as e:
            logger.error(f"Failed to record no_response signals: {e}")

    return count


def compute_capacity_fit(venue_capacity: Optional[int], max_attendance: int) -> str:
    """
    Compute capacity fit indicator.
    Green: 100-150% of max attendance → good_fit
    Yellow: 80-99% or 151-200% → tight_fit / oversized
    Red: <80% or >200% → poor_fit
    """
    if not venue_capacity or not max_attendance:
        return "poor_fit"

    ratio = venue_capacity / max_attendance

    if 1.0 <= ratio <= 1.5:
        return "good_fit"
    elif 0.8 <= ratio < 1.0:
        return "tight_fit"
    elif 1.5 < ratio <= 2.0:
        return "oversized"
    else:
        return "poor_fit"


def compute_amenity_match(
    db: Session,
    venue_id: str,
    required_amenity_ids: List[str],
) -> float:
    """Compute amenity match percentage."""
    if not required_amenity_ids:
        return 100.0

    venue_amenity_ids = set(
        row[0]
        for row in db.query(VenueAmenity.amenity_id)
        .filter(VenueAmenity.venue_id == venue_id)
        .all()
    )

    matched = len(set(required_amenity_ids) & venue_amenity_ids)
    return round((matched / len(required_amenity_ids)) * 100, 1)


def get_pre_send_summary(db: Session, *, rfp: RFP) -> List[dict]:
    """Get pre-send fit indicators for all selected venues."""
    rfp_venues = (
        db.query(RFPVenue)
        .options(joinedload(RFPVenue.venue))
        .filter(RFPVenue.rfp_id == rfp.id)
        .all()
    )

    required_ids = rfp.required_amenity_ids or []

    # Batch load amenity names
    amenity_names = {}
    if required_ids:
        rows = (
            db.query(Amenity.id, Amenity.name)
            .filter(Amenity.id.in_(required_ids))
            .all()
        )
        amenity_names = {r.id: r.name for r in rows}

    # Batch load venue amenity IDs
    venue_ids = [rv.venue_id for rv in rfp_venues]
    venue_amenity_map = {}
    if venue_ids:
        rows = (
            db.query(VenueAmenity.venue_id, VenueAmenity.amenity_id)
            .filter(VenueAmenity.venue_id.in_(venue_ids))
            .all()
        )
        for r in rows:
            venue_amenity_map.setdefault(r.venue_id, set()).add(r.amenity_id)

    # Batch load min full_day prices
    min_prices = {}
    if venue_ids:
        price_rows = (
            db.query(
                VenueSpace.venue_id,
                func.min(VenueSpacePricing.amount).label("min_amount"),
                VenueSpacePricing.currency,
            )
            .join(VenueSpacePricing, VenueSpacePricing.space_id == VenueSpace.id)
            .filter(
                VenueSpace.venue_id.in_(venue_ids),
                VenueSpacePricing.rate_type == "full_day",
            )
            .group_by(VenueSpace.venue_id, VenueSpacePricing.currency)
            .all()
        )
        for r in price_rows:
            if r.venue_id not in min_prices or float(r.min_amount) < min_prices[r.venue_id]["amount"]:
                min_prices[r.venue_id] = {"amount": float(r.min_amount), "currency": r.currency}

    result = []
    for rv in rfp_venues:
        venue = rv.venue
        v_amenities = venue_amenity_map.get(venue.id, set())
        required_set = set(required_ids)

        matched = required_set & v_amenities
        missing = required_set - v_amenities

        matched_names = [amenity_names.get(a, a) for a in matched]
        missing_names = [amenity_names.get(a, a) for a in missing]

        cap_fit = compute_capacity_fit(venue.total_capacity, rfp.attendance_max)
        amenity_pct = round((len(matched) / len(required_set)) * 100, 1) if required_set else 100.0

        # Capacity fit color
        if cap_fit == "good_fit":
            cap_color = "green"
        elif cap_fit in ("tight_fit", "oversized"):
            cap_color = "yellow"
        else:
            cap_color = "red"

        # Amenity match color
        if amenity_pct >= 80:
            amenity_color = "green"
        elif amenity_pct >= 50:
            amenity_color = "yellow"
        else:
            amenity_color = "red"

        # Price indicator
        price_info = min_prices.get(venue.id)
        if price_info and rfp.budget_min is not None and rfp.budget_max is not None:
            amt = price_info["amount"]
            bmin = float(rfp.budget_min)
            bmax = float(rfp.budget_max)
            if bmin <= amt <= bmax:
                price_indicator = "within_budget"
                price_detail = (
                    f"Full-day rate: {price_info['currency']} {amt:,.0f} "
                    f"(budget: {rfp.budget_currency} {bmin:,.0f} - {bmax:,.0f})"
                )
            elif amt < bmin:
                price_indicator = "below_budget"
                price_detail = (
                    f"Full-day rate: {price_info['currency']} {amt:,.0f} "
                    f"(below budget min {rfp.budget_currency} {bmin:,.0f})"
                )
            else:
                price_indicator = "above_budget"
                price_detail = (
                    f"Full-day rate: {price_info['currency']} {amt:,.0f} "
                    f"(above budget max {rfp.budget_currency} {bmax:,.0f})"
                )
        else:
            price_indicator = "no_data"
            price_detail = None

        result.append({
            "venue_id": venue.id,
            "venue_name": venue.name,
            "venue_capacity": venue.total_capacity,
            "capacity_fit": cap_fit,
            "capacity_fit_color": cap_color,
            "amenity_match_pct": amenity_pct,
            "amenity_match_color": amenity_color,
            "matched_amenities": matched_names,
            "missing_amenities": missing_names,
            "price_indicator": price_indicator,
            "price_indicator_detail": price_detail,
        })

    return result
