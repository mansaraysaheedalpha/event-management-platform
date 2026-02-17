# app/crud/crud_rfp.py
import math
from typing import Optional, List
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func

from app.models.rfp import RFP
from app.models.rfp_venue import RFPVenue
from app.models.venue_response import VenueResponse
from app.schemas.rfp import RFPCreate, RFPUpdate

# Active (non-terminal) statuses — these count toward the 5-RFP limit
ACTIVE_STATUSES = {"draft", "sent", "collecting_responses", "review"}
TERMINAL_STATUSES = {"awarded", "closed", "expired"}

# Valid state transitions
VALID_TRANSITIONS = {
    "draft": {"sent"},
    "sent": {"collecting_responses", "closed", "expired"},
    "collecting_responses": {"review", "closed"},
    "review": {"awarded", "closed"},
    # Terminal states have no outgoing transitions
}


def count_active_rfps(db: Session, org_id: str) -> int:
    return (
        db.query(func.count(RFP.id))
        .filter(RFP.organization_id == org_id, RFP.status.in_(ACTIVE_STATUSES))
        .scalar()
    )


def create(db: Session, *, org_id: str, data: RFPCreate) -> RFP:
    obj_data = data.model_dump()
    # Convert Decimal fields to float for JSON-compatible storage
    for field in ("budget_min", "budget_max"):
        if obj_data.get(field) is not None:
            obj_data[field] = obj_data[field]

    db_obj = RFP(
        **obj_data,
        organization_id=org_id,
        status="draft",
    )
    db.add(db_obj)
    db.commit()
    db.refresh(db_obj)
    return db_obj


def get(db: Session, rfp_id: str) -> Optional[RFP]:
    return (
        db.query(RFP)
        .options(
            joinedload(RFP.venues).joinedload(RFPVenue.venue),
            joinedload(RFP.venues).joinedload(RFPVenue.response),
        )
        .filter(RFP.id == rfp_id)
        .first()
    )


def get_simple(db: Session, rfp_id: str) -> Optional[RFP]:
    """Get RFP without eager loading relationships."""
    return db.query(RFP).filter(RFP.id == rfp_id).first()


def list_by_org(
    db: Session,
    org_id: str,
    status: Optional[str] = None,
    page: int = 1,
    page_size: int = 10,
) -> dict:
    page_size = min(page_size, 50)
    query = db.query(RFP).filter(RFP.organization_id == org_id)

    if status:
        query = query.filter(RFP.status == status)

    total_count = query.count()
    total_pages = math.ceil(total_count / page_size) if page_size > 0 else 0
    offset = (page - 1) * page_size

    rfps = query.order_by(RFP.created_at.desc()).offset(offset).limit(page_size).all()

    # Batch-load venue counts and response counts
    rfp_ids = [r.id for r in rfps]

    venue_counts = dict(
        db.query(RFPVenue.rfp_id, func.count(RFPVenue.id))
        .filter(RFPVenue.rfp_id.in_(rfp_ids))
        .group_by(RFPVenue.rfp_id)
        .all()
    ) if rfp_ids else {}

    response_counts = dict(
        db.query(RFPVenue.rfp_id, func.count(RFPVenue.id))
        .filter(
            RFPVenue.rfp_id.in_(rfp_ids),
            RFPVenue.status == "responded",
        )
        .group_by(RFPVenue.rfp_id)
        .all()
    ) if rfp_ids else {}

    items = []
    for r in rfps:
        items.append({
            "id": r.id,
            "title": r.title,
            "event_type": r.event_type,
            "status": r.status,
            "attendance_max": r.attendance_max,
            "preferred_dates_start": r.preferred_dates_start,
            "response_deadline": r.response_deadline,
            "venue_count": venue_counts.get(r.id, 0),
            "response_count": response_counts.get(r.id, 0),
            "sent_at": r.sent_at,
            "created_at": r.created_at,
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


def update(db: Session, *, rfp: RFP, data: RFPUpdate) -> RFP:
    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(rfp, field, value)
    db.commit()
    db.refresh(rfp)
    return rfp


def delete(db: Session, *, rfp: RFP) -> None:
    db.delete(rfp)
    db.commit()


def transition_status(rfp: RFP, new_status: str) -> bool:
    """Validate and apply a status transition. Returns True if valid."""
    allowed = VALID_TRANSITIONS.get(rfp.status, set())
    if new_status not in allowed:
        return False
    rfp.status = new_status
    return True


def send(db: Session, *, rfp: RFP) -> RFP:
    rfp.status = "sent"
    rfp.sent_at = datetime.now(timezone.utc)

    # Set notified_at on all venues
    for rv in rfp.venues:
        rv.notified_at = rfp.sent_at

    db.commit()
    db.refresh(rfp)
    return rfp


def extend_deadline(db: Session, *, rfp: RFP, new_deadline: datetime) -> RFP:
    rfp.response_deadline = new_deadline
    db.commit()
    db.refresh(rfp)
    return rfp


def close(db: Session, *, rfp: RFP) -> RFP:
    rfp.status = "closed"
    db.commit()
    db.refresh(rfp)
    return rfp


def duplicate(db: Session, *, rfp: RFP) -> RFP:
    new_rfp = RFP(
        organization_id=rfp.organization_id,
        title=f"{rfp.title} (Copy)",
        event_type=rfp.event_type,
        attendance_min=rfp.attendance_min,
        attendance_max=rfp.attendance_max,
        preferred_dates_start=rfp.preferred_dates_start,
        preferred_dates_end=rfp.preferred_dates_end,
        dates_flexible=rfp.dates_flexible,
        duration=rfp.duration,
        space_requirements=rfp.space_requirements,
        required_amenity_ids=rfp.required_amenity_ids,
        catering_needs=rfp.catering_needs,
        budget_min=rfp.budget_min,
        budget_max=rfp.budget_max,
        budget_currency=rfp.budget_currency,
        preferred_currency=rfp.preferred_currency,
        additional_notes=rfp.additional_notes,
        response_deadline=datetime.now(timezone.utc) + timedelta(days=7),
        linked_event_id=rfp.linked_event_id,
        status="draft",
    )
    db.add(new_rfp)
    db.commit()
    db.refresh(new_rfp)
    return new_rfp
