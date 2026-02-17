# app/graphql/rfp_mutations.py
"""GraphQL RFP system mutations — called from the main Mutation class."""
from typing import Optional, List
from datetime import datetime, timezone, date, timedelta
from decimal import Decimal
from strawberry.types import Info
from fastapi import HTTPException

from ..crud import crud_rfp, crud_rfp_venue, crud_venue_response
from ..schemas.rfp import RFPCreate, RFPUpdate
from ..schemas.venue_response import VenueResponseCreate, ExtraCostAmenity
from .rfp_types import (
    RFPType,
    RFPVenueType,
    VenueResponseType,
    RFPCreateInput,
    RFPUpdateInput,
    VenueResponseInput,
)
from .rfp_queries import _rfp_to_gql, _response_to_gql


def _get_user_org(info: Info) -> tuple:
    user = info.context.user
    if not user or not user.get("orgId"):
        raise HTTPException(status_code=403, detail="Not authorized")
    return user, user["orgId"]


def _parse_date(date_str: Optional[str]) -> Optional[date]:
    if not date_str:
        return None
    return date.fromisoformat(date_str)


# ── RFP CRUD Mutations ────────────────────────────────────────────────

def create_rfp_mutation(input: RFPCreateInput, info: Info) -> RFPType:
    user, org_id = _get_user_org(info)
    db = info.context.db

    active_count = crud_rfp.count_active_rfps(db, org_id)
    if active_count >= 5:
        raise HTTPException(
            status_code=429,
            detail="Maximum 5 active RFPs per organizer.",
        )

    create_data = RFPCreate(
        title=input.title,
        event_type=input.eventType,
        attendance_min=input.attendanceMin,
        attendance_max=input.attendanceMax,
        preferred_dates_start=_parse_date(input.preferredDatesStart),
        preferred_dates_end=_parse_date(input.preferredDatesEnd),
        dates_flexible=input.datesFlexible or False,
        duration=input.duration,
        space_requirements=input.spaceRequirements or [],
        required_amenity_ids=input.requiredAmenityIds or [],
        catering_needs=input.cateringNeeds,
        budget_min=Decimal(str(input.budgetMin)) if input.budgetMin is not None else None,
        budget_max=Decimal(str(input.budgetMax)) if input.budgetMax is not None else None,
        budget_currency=input.budgetCurrency,
        preferred_currency=input.preferredCurrency or "USD",
        additional_notes=input.additionalNotes,
        response_deadline=input.responseDeadline,
        linked_event_id=input.linkedEventId,
    )

    rfp = crud_rfp.create(db, org_id=org_id, data=create_data)
    rfp = crud_rfp.get(db, rfp.id)
    return _rfp_to_gql(db, rfp)


def update_rfp_mutation(id: str, input: RFPUpdateInput, info: Info) -> RFPType:
    user, org_id = _get_user_org(info)
    db = info.context.db

    rfp = crud_rfp.get_simple(db, id)
    if not rfp or rfp.organization_id != org_id:
        raise HTTPException(status_code=404, detail="RFP not found")

    if rfp.status != "draft":
        raise HTTPException(status_code=422, detail="Can only update draft RFPs")

    # Build update data from non-None fields
    update_dict = {}
    if input.title is not None:
        update_dict["title"] = input.title
    if input.eventType is not None:
        update_dict["event_type"] = input.eventType
    if input.attendanceMin is not None:
        update_dict["attendance_min"] = input.attendanceMin
    if input.attendanceMax is not None:
        update_dict["attendance_max"] = input.attendanceMax
    if input.preferredDatesStart is not None:
        update_dict["preferred_dates_start"] = _parse_date(input.preferredDatesStart)
    if input.preferredDatesEnd is not None:
        update_dict["preferred_dates_end"] = _parse_date(input.preferredDatesEnd)
    if input.datesFlexible is not None:
        update_dict["dates_flexible"] = input.datesFlexible
    if input.duration is not None:
        update_dict["duration"] = input.duration
    if input.spaceRequirements is not None:
        update_dict["space_requirements"] = input.spaceRequirements
    if input.requiredAmenityIds is not None:
        update_dict["required_amenity_ids"] = input.requiredAmenityIds
    if input.cateringNeeds is not None:
        update_dict["catering_needs"] = input.cateringNeeds
    if input.budgetMin is not None:
        update_dict["budget_min"] = Decimal(str(input.budgetMin))
    if input.budgetMax is not None:
        update_dict["budget_max"] = Decimal(str(input.budgetMax))
    if input.budgetCurrency is not None:
        update_dict["budget_currency"] = input.budgetCurrency
    if input.preferredCurrency is not None:
        update_dict["preferred_currency"] = input.preferredCurrency
    if input.additionalNotes is not None:
        update_dict["additional_notes"] = input.additionalNotes
    if input.responseDeadline is not None:
        update_dict["response_deadline"] = input.responseDeadline
    if input.linkedEventId is not None:
        update_dict["linked_event_id"] = input.linkedEventId

    update_schema = RFPUpdate(**update_dict)
    rfp = crud_rfp.update(db, rfp=rfp, data=update_schema)
    rfp = crud_rfp.get(db, rfp.id)
    return _rfp_to_gql(db, rfp)


def delete_rfp_mutation(id: str, info: Info) -> bool:
    user, org_id = _get_user_org(info)
    db = info.context.db

    rfp = crud_rfp.get_simple(db, id)
    if not rfp or rfp.organization_id != org_id:
        raise HTTPException(status_code=404, detail="RFP not found")

    if rfp.status != "draft":
        raise HTTPException(status_code=422, detail="Can only delete draft RFPs")

    crud_rfp.delete(db, rfp=rfp)
    return True


# ── Venue Selection Mutations ─────────────────────────────────────────

def add_venues_to_rfp_mutation(
    rfpId: str,
    venueIds: List[str],
    info: Info,
) -> List[RFPVenueType]:
    user, org_id = _get_user_org(info)
    db = info.context.db

    rfp = crud_rfp.get(db, rfpId)
    if not rfp or rfp.organization_id != org_id:
        raise HTTPException(status_code=404, detail="RFP not found")

    if rfp.status != "draft":
        raise HTTPException(status_code=422, detail="Can only add venues to draft RFPs")

    current_count = crud_rfp_venue.count_venues_for_rfp(db, rfpId)
    if current_count + len(venueIds) > 10:
        raise HTTPException(status_code=409, detail="Maximum 10 venues per RFP")

    result = crud_rfp_venue.add_venues(db, rfp=rfp, venue_ids=venueIds)

    return [
        RFPVenueType(
            id=item["id"],
            rfpId=rfpId,
            venueId=item["venue_id"],
            venueName=item["venue_name"],
            status=item["status"],
            capacityFit=item["capacity_fit"],
            amenityMatchPct=item["amenity_match_pct"],
            hasResponse=False,
        )
        for item in result["added"]
    ]


def remove_venue_from_rfp_mutation(rfpId: str, venueId: str, info: Info) -> bool:
    user, org_id = _get_user_org(info)
    db = info.context.db

    rfp = crud_rfp.get_simple(db, rfpId)
    if not rfp or rfp.organization_id != org_id:
        raise HTTPException(status_code=404, detail="RFP not found")

    if rfp.status != "draft":
        raise HTTPException(status_code=422, detail="Can only remove venues from draft RFPs")

    return crud_rfp_venue.remove_venue(db, rfp_id=rfpId, venue_id=venueId)


# ── RFP Action Mutations ─────────────────────────────────────────────

def send_rfp_mutation(id: str, info: Info) -> RFPType:
    user, org_id = _get_user_org(info)
    db = info.context.db

    rfp = crud_rfp.get(db, id)
    if not rfp or rfp.organization_id != org_id:
        raise HTTPException(status_code=404, detail="RFP not found")

    if rfp.status != "draft":
        raise HTTPException(status_code=422, detail="Can only send draft RFPs")

    if not rfp.venues:
        raise HTTPException(status_code=422, detail="RFP must have at least 1 venue")

    if rfp.response_deadline <= datetime.now(timezone.utc):
        raise HTTPException(status_code=422, detail="Response deadline must be in the future")

    rfp = crud_rfp.send(db, rfp=rfp)

    try:
        from ..utils.rfp_notifications import dispatch_rfp_send_notifications
        dispatch_rfp_send_notifications(db, rfp)
    except Exception:
        pass

    rfp = crud_rfp.get(db, rfp.id)
    return _rfp_to_gql(db, rfp)


def extend_rfp_deadline_mutation(id: str, newDeadline: datetime, info: Info) -> RFPType:
    user, org_id = _get_user_org(info)
    db = info.context.db

    rfp = crud_rfp.get_simple(db, id)
    if not rfp or rfp.organization_id != org_id:
        raise HTTPException(status_code=404, detail="RFP not found")

    if rfp.status not in ("sent", "collecting_responses"):
        raise HTTPException(status_code=422, detail="Cannot extend deadline for this RFP status")

    if newDeadline <= rfp.response_deadline:
        raise HTTPException(status_code=422, detail="New deadline must be after current deadline")

    rfp = crud_rfp.extend_deadline(db, rfp=rfp, new_deadline=newDeadline)
    rfp = crud_rfp.get(db, rfp.id)
    return _rfp_to_gql(db, rfp)


def close_rfp_mutation(id: str, info: Info, reason: Optional[str] = None) -> RFPType:
    user, org_id = _get_user_org(info)
    db = info.context.db

    rfp = crud_rfp.get_simple(db, id)
    if not rfp or rfp.organization_id != org_id:
        raise HTTPException(status_code=404, detail="RFP not found")

    if rfp.status not in ("sent", "collecting_responses", "review"):
        raise HTTPException(status_code=422, detail="Cannot close RFP with this status")

    rfp = crud_rfp.close(db, rfp=rfp)
    rfp = crud_rfp.get(db, rfp.id)
    return _rfp_to_gql(db, rfp)


def duplicate_rfp_mutation(id: str, info: Info) -> RFPType:
    user, org_id = _get_user_org(info)
    db = info.context.db

    rfp = crud_rfp.get_simple(db, id)
    if not rfp or rfp.organization_id != org_id:
        raise HTTPException(status_code=404, detail="RFP not found")

    new_rfp = crud_rfp.duplicate(db, rfp=rfp)
    new_rfp = crud_rfp.get(db, new_rfp.id)
    return _rfp_to_gql(db, new_rfp)


# ── Venue Decision Mutations ─────────────────────────────────────────

def shortlist_venue_mutation(rfpId: str, rfvId: str, info: Info) -> RFPVenueType:
    user, org_id = _get_user_org(info)
    db = info.context.db

    rfp = crud_rfp.get_simple(db, rfpId)
    if not rfp or rfp.organization_id != org_id:
        raise HTTPException(status_code=404, detail="RFP not found")

    rfv = crud_rfp_venue.get(db, rfvId)
    if not rfv or rfv.rfp_id != rfpId:
        raise HTTPException(status_code=404, detail="RFP-Venue junction not found")

    if rfv.status != "responded":
        raise HTTPException(status_code=422, detail="Can only shortlist venues that have responded")

    rfv = crud_rfp_venue.shortlist(db, rfv=rfv)
    venue = rfv.venue

    return RFPVenueType(
        id=rfv.id, rfpId=rfv.rfp_id, venueId=rfv.venue_id,
        venueName=venue.name if venue else "Unknown",
        status=rfv.status, capacityFit=rfv.capacity_fit,
        amenityMatchPct=rfv.amenity_match_pct,
        respondedAt=rfv.responded_at, hasResponse=rfv.response is not None,
    )


def award_venue_mutation(rfpId: str, rfvId: str, info: Info) -> RFPVenueType:
    user, org_id = _get_user_org(info)
    db = info.context.db

    rfp = crud_rfp.get_simple(db, rfpId)
    if not rfp or rfp.organization_id != org_id:
        raise HTTPException(status_code=404, detail="RFP not found")

    rfv = crud_rfp_venue.get(db, rfvId)
    if not rfv or rfv.rfp_id != rfpId:
        raise HTTPException(status_code=404, detail="RFP-Venue junction not found")

    if rfv.status not in ("responded", "shortlisted"):
        raise HTTPException(status_code=422, detail="Can only award responded/shortlisted venues")

    # Check no already awarded
    from ..models.rfp_venue import RFPVenue
    already = db.query(RFPVenue).filter(RFPVenue.rfp_id == rfpId, RFPVenue.status == "awarded").first()
    if already:
        raise HTTPException(status_code=409, detail="Another venue already awarded")

    rfv = crud_rfp_venue.award(db, rfv=rfv, rfp=rfp)
    venue = rfv.venue

    try:
        from ..utils.rfp_notifications import dispatch_proposal_accepted_notification
        dispatch_proposal_accepted_notification(db, rfv)
    except Exception:
        pass

    return RFPVenueType(
        id=rfv.id, rfpId=rfv.rfp_id, venueId=rfv.venue_id,
        venueName=venue.name if venue else "Unknown",
        status=rfv.status, capacityFit=rfv.capacity_fit,
        amenityMatchPct=rfv.amenity_match_pct,
        respondedAt=rfv.responded_at, hasResponse=rfv.response is not None,
    )


def decline_venue_mutation(rfpId: str, rfvId: str, info: Info, reason: Optional[str] = None) -> RFPVenueType:
    user, org_id = _get_user_org(info)
    db = info.context.db

    rfp = crud_rfp.get_simple(db, rfpId)
    if not rfp or rfp.organization_id != org_id:
        raise HTTPException(status_code=404, detail="RFP not found")

    rfv = crud_rfp_venue.get(db, rfvId)
    if not rfv or rfv.rfp_id != rfpId:
        raise HTTPException(status_code=404, detail="RFP-Venue junction not found")

    if rfv.status not in ("responded", "shortlisted"):
        raise HTTPException(status_code=422, detail="Can only decline responded/shortlisted venues")

    rfv = crud_rfp_venue.decline(db, rfv=rfv)
    venue = rfv.venue

    try:
        from ..utils.rfp_notifications import dispatch_proposal_declined_notification
        dispatch_proposal_declined_notification(db, rfv, reason=reason)
    except Exception:
        pass

    return RFPVenueType(
        id=rfv.id, rfpId=rfv.rfp_id, venueId=rfv.venue_id,
        venueName=venue.name if venue else "Unknown",
        status=rfv.status, capacityFit=rfv.capacity_fit,
        amenityMatchPct=rfv.amenity_match_pct,
        respondedAt=rfv.responded_at, hasResponse=rfv.response is not None,
    )


# ── Venue Owner Response Mutation ─────────────────────────────────────

def submit_venue_response_mutation(
    venueId: str,
    rfpId: str,
    input: VenueResponseInput,
    info: Info,
) -> VenueResponseType:
    user, org_id = _get_user_org(info)
    db = info.context.db

    from ..models.venue import Venue
    venue = db.query(Venue).filter(Venue.id == venueId).first()
    if not venue or venue.organization_id != org_id:
        raise HTTPException(status_code=403, detail="Not authorized")

    rfv = crud_rfp_venue.get_rfv_for_venue_rfp(db, venueId, rfpId)
    if not rfv:
        raise HTTPException(status_code=404, detail="RFP not found for this venue")

    rfp = rfv.rfp

    if rfv.status not in ("received", "viewed"):
        raise HTTPException(status_code=409, detail="Already responded or declined")

    if rfp.response_deadline <= datetime.now(timezone.utc):
        raise HTTPException(status_code=422, detail="Response deadline has passed")

    existing = crud_venue_response.get_by_rfp_venue(db, rfv.id)
    if existing:
        raise HTTPException(status_code=409, detail="Already responded")

    # Convert GQL input to Pydantic schema
    extra_cost_amenities = []
    if input.extraCostAmenities:
        extra_cost_amenities = [
            ExtraCostAmenity(amenity_id=eca.amenityId, name=eca.name, price=eca.price)
            for eca in input.extraCostAmenities
        ]

    create_data = VenueResponseCreate(
        availability=input.availability,
        proposed_space_id=input.proposedSpaceId,
        currency=input.currency,
        space_rental_price=Decimal(str(input.spaceRentalPrice)) if input.spaceRentalPrice is not None else None,
        catering_price_per_head=Decimal(str(input.cateringPricePerHead)) if input.cateringPricePerHead is not None else None,
        av_equipment_fees=Decimal(str(input.avEquipmentFees)) if input.avEquipmentFees is not None else None,
        setup_cleanup_fees=Decimal(str(input.setupCleanupFees)) if input.setupCleanupFees is not None else None,
        other_fees=Decimal(str(input.otherFees)) if input.otherFees is not None else None,
        other_fees_description=input.otherFeesDescription,
        included_amenity_ids=input.includedAmenityIds or [],
        extra_cost_amenities=extra_cost_amenities,
        cancellation_policy=input.cancellationPolicy,
        deposit_amount=Decimal(str(input.depositAmount)) if input.depositAmount is not None else None,
        payment_schedule=input.paymentSchedule,
        alternative_dates=input.alternativeDates,
        quote_valid_until=_parse_date(input.quoteValidUntil),
        notes=input.notes,
    )

    response = crud_venue_response.create(db, rfp_venue=rfv, rfp=rfp, data=create_data)

    try:
        from ..utils.rfp_notifications import dispatch_venue_responded_notification
        dispatch_venue_responded_notification(db, rfv, rfp)
    except Exception:
        pass

    return _response_to_gql(response)
