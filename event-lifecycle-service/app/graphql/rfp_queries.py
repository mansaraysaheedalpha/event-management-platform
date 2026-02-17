# app/graphql/rfp_queries.py
"""GraphQL RFP system queries — called from the main Query class."""
from typing import Optional, List
from datetime import datetime
from strawberry.types import Info
from fastapi import HTTPException

from ..crud import crud_rfp, crud_rfp_venue, crud_venue_response
from ..models.amenity import Amenity
from ..models.amenity_category import AmenityCategory
from ..models.rfp_venue import RFPVenue
from ..models.venue_photo import VenuePhoto
from ..models.venue_space import VenueSpace
from .rfp_types import (
    RFPType,
    RFPListResultType,
    RFPAmenityType,
    RFPVenueType,
    VenueResponseType,
    ExtraCostAmenityType,
    ComparisonDashboardType,
    ComparisonVenueType,
    ComparisonVenueResponseType,
    ComparisonBadgesType,
    ExchangeRateType,
    PreSendSummaryType,
    PreSendVenueFitType,
    VenueRFPInboxResultType,
    VenueRFPInboxItemType,
    VenueRFPDetailType,
    VenueRFPSpaceType,
)


def _get_user_org(info: Info) -> tuple:
    user = info.context.user
    if not user or not user.get("orgId"):
        raise HTTPException(status_code=403, detail="Not authorized")
    return user, user["orgId"]


def _response_to_gql(resp) -> Optional[VenueResponseType]:
    """Convert a VenueResponse model to GQL type."""
    if not resp:
        return None

    extra_costs = []
    for eca in (resp.extra_cost_amenities or []):
        if isinstance(eca, dict):
            extra_costs.append(ExtraCostAmenityType(
                amenityId=eca.get("amenity_id", ""),
                name=eca.get("name", ""),
                price=eca.get("price", 0),
            ))

    return VenueResponseType(
        id=resp.id,
        availability=resp.availability,
        proposedSpaceName=resp.proposed_space_name,
        proposedSpaceCapacity=resp.proposed_space_capacity,
        currency=resp.currency,
        spaceRentalPrice=float(resp.space_rental_price) if resp.space_rental_price else None,
        cateringPricePerHead=float(resp.catering_price_per_head) if resp.catering_price_per_head else None,
        avEquipmentFees=float(resp.av_equipment_fees) if resp.av_equipment_fees else None,
        setupCleanupFees=float(resp.setup_cleanup_fees) if resp.setup_cleanup_fees else None,
        otherFees=float(resp.other_fees) if resp.other_fees else None,
        otherFeesDescription=resp.other_fees_description,
        totalEstimatedCost=float(resp.total_estimated_cost),
        includedAmenityIds=resp.included_amenity_ids or [],
        extraCostAmenities=extra_costs,
        cancellationPolicy=resp.cancellation_policy,
        depositAmount=float(resp.deposit_amount) if resp.deposit_amount else None,
        paymentSchedule=resp.payment_schedule,
        alternativeDates=resp.alternative_dates,
        quoteValidUntil=str(resp.quote_valid_until) if resp.quote_valid_until else None,
        notes=resp.notes,
        createdAt=resp.created_at,
    )


def _rfp_to_gql(db, rfp) -> RFPType:
    """Convert an RFP model (with loaded relations) to GQL type."""
    # Resolve amenities
    required_amenities = []
    if rfp.required_amenity_ids:
        amenity_rows = (
            db.query(Amenity.id, Amenity.name, AmenityCategory.name.label("category"))
            .join(AmenityCategory, AmenityCategory.id == Amenity.category_id)
            .filter(Amenity.id.in_(rfp.required_amenity_ids))
            .all()
        )
        required_amenities = [
            RFPAmenityType(id=a.id, name=a.name, category=a.category)
            for a in amenity_rows
        ]

    # Build venues
    venues = []
    response_count = 0
    for rv in (rfp.venues or []):
        venue = rv.venue
        cover_photo_url = None
        if venue:
            cover = db.query(VenuePhoto.url).filter(
                VenuePhoto.venue_id == venue.id, VenuePhoto.is_cover == True
            ).first()
            if cover:
                cover_photo_url = cover.url

        has_response = rv.response is not None
        if has_response:
            response_count += 1

        venues.append(RFPVenueType(
            id=rv.id,
            rfpId=rv.rfp_id,
            venueId=rv.venue_id,
            venueName=venue.name if venue else "Unknown",
            venueSlug=venue.slug if venue else None,
            venueCity=venue.city if venue else None,
            venueCountry=venue.country if venue else None,
            venueVerified=venue.verified if venue else False,
            venueCoverPhotoUrl=cover_photo_url,
            status=rv.status,
            capacityFit=rv.capacity_fit,
            amenityMatchPct=rv.amenity_match_pct,
            notifiedAt=rv.notified_at,
            viewedAt=rv.viewed_at,
            respondedAt=rv.responded_at,
            hasResponse=has_response,
            response=_response_to_gql(rv.response),
        ))

    return RFPType(
        id=rfp.id,
        organizationId=rfp.organization_id,
        title=rfp.title,
        eventType=rfp.event_type,
        attendanceMin=rfp.attendance_min,
        attendanceMax=rfp.attendance_max,
        preferredDatesStart=str(rfp.preferred_dates_start) if rfp.preferred_dates_start else None,
        preferredDatesEnd=str(rfp.preferred_dates_end) if rfp.preferred_dates_end else None,
        datesFlexible=rfp.dates_flexible,
        duration=rfp.duration,
        spaceRequirements=rfp.space_requirements or [],
        requiredAmenities=required_amenities,
        cateringNeeds=rfp.catering_needs,
        budgetMin=float(rfp.budget_min) if rfp.budget_min else None,
        budgetMax=float(rfp.budget_max) if rfp.budget_max else None,
        budgetCurrency=rfp.budget_currency,
        preferredCurrency=rfp.preferred_currency,
        additionalNotes=rfp.additional_notes,
        responseDeadline=rfp.response_deadline,
        linkedEventId=rfp.linked_event_id,
        status=rfp.status,
        sentAt=rfp.sent_at,
        createdAt=rfp.created_at,
        updatedAt=rfp.updated_at,
        venues=venues,
        venueCount=len(venues),
        responseCount=response_count,
    )


# ── Queries ───────────────────────────────────────────────────────────

def organization_rfps_query(
    info: Info,
    status: Optional[str] = None,
    page: int = 1,
    pageSize: int = 10,
) -> RFPListResultType:
    user, org_id = _get_user_org(info)
    db = info.context.db

    result = crud_rfp.list_by_org(db, org_id, status=status, page=page, page_size=pageSize)

    rfp_items = []
    for item in result["rfps"]:
        rfp_items.append(RFPType(
            id=item["id"],
            organizationId=org_id,
            title=item["title"],
            eventType=item["event_type"],
            attendanceMin=0,
            attendanceMax=item["attendance_max"],
            duration="",
            cateringNeeds="",
            responseDeadline=item["response_deadline"],
            status=item["status"],
            sentAt=item.get("sent_at"),
            createdAt=item["created_at"],
            venueCount=item["venue_count"],
            responseCount=item["response_count"],
            preferredDatesStart=str(item["preferred_dates_start"]) if item.get("preferred_dates_start") else None,
        ))

    pagination = result["pagination"]
    return RFPListResultType(
        rfps=rfp_items,
        totalCount=pagination["total_count"],
        page=pagination["page"],
        pageSize=pagination["page_size"],
        totalPages=pagination["total_pages"],
    )


def rfp_query(id: str, info: Info) -> Optional[RFPType]:
    user, org_id = _get_user_org(info)
    db = info.context.db

    rfp = crud_rfp.get(db, id)
    if not rfp or rfp.organization_id != org_id:
        return None

    return _rfp_to_gql(db, rfp)


def rfp_comparison_query(rfpId: str, info: Info) -> ComparisonDashboardType:
    user, org_id = _get_user_org(info)
    db = info.context.db

    rfp = crud_rfp.get(db, rfpId)
    if not rfp or rfp.organization_id != org_id:
        raise HTTPException(status_code=404, detail="RFP not found")

    raw_data = crud_venue_response.get_comparison_data(db, rfp=rfp)

    # Fetch exchange rates
    exchange_rates_gql = None
    try:
        from ..utils.exchange_rates import get_exchange_rates_sync
        er_data = get_exchange_rates_sync(rfp.preferred_currency)
        if er_data:
            exchange_rates_gql = ExchangeRateType(
                base=er_data["base"],
                rates=er_data["rates"],
                fetchedAt=er_data["fetched_at"],
            )
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
        total_in_preferred = total_cost

        amenity_pct = item["amenity_match_pct"]
        if best_value_cost is None or total_in_preferred < best_value_cost:
            best_value_cost = total_in_preferred
            best_value_rfv = item["rfv_id"]
        if amenity_pct > best_match_pct:
            best_match_pct = amenity_pct
            best_match_rfv = item["rfv_id"]

        extra_costs = []
        for eca in (resp.extra_cost_amenities or []):
            if isinstance(eca, dict):
                extra_costs.append(ExtraCostAmenityType(
                    amenityId=eca.get("amenity_id", ""),
                    name=eca.get("name", ""),
                    price=eca.get("price", 0),
                ))

        comp_resp = ComparisonVenueResponseType(
            id=resp.id,
            availability=resp.availability,
            proposedSpaceName=resp.proposed_space_name,
            proposedSpaceCapacity=resp.proposed_space_capacity,
            currency=resp.currency,
            spaceRentalPrice=float(resp.space_rental_price) if resp.space_rental_price else None,
            cateringPricePerHead=float(resp.catering_price_per_head) if resp.catering_price_per_head else None,
            avEquipmentFees=float(resp.av_equipment_fees) if resp.av_equipment_fees else None,
            setupCleanupFees=float(resp.setup_cleanup_fees) if resp.setup_cleanup_fees else None,
            otherFees=float(resp.other_fees) if resp.other_fees else None,
            totalEstimatedCost=total_cost,
            totalInPreferredCurrency=round(total_in_preferred, 2),
            includedAmenityIds=resp.included_amenity_ids or [],
            extraCostAmenities=extra_costs,
            depositAmount=float(resp.deposit_amount) if resp.deposit_amount else None,
            quoteValidUntil=str(resp.quote_valid_until) if resp.quote_valid_until else None,
            cancellationPolicy=resp.cancellation_policy,
            createdAt=resp.created_at,
        )

        venues.append(ComparisonVenueType(
            rfvId=item["rfv_id"],
            venueId=item["venue_id"],
            venueName=item["venue_name"],
            venueVerified=item["venue_verified"],
            venueSlug=item["venue_slug"],
            status=item["status"],
            response=comp_resp,
            totalInPreferredCurrency=round(total_in_preferred, 2),
            amenityMatchPct=amenity_pct,
            responseTimeHours=item["response_time_hours"],
            badges=[],
        ))

    # Assign badges
    for v in venues:
        if v.rfvId == best_value_rfv:
            v.badges.append("best_value")
        if v.rfvId == best_match_rfv:
            v.badges.append("best_match")

    return ComparisonDashboardType(
        rfpId=rfp.id,
        preferredCurrency=rfp.preferred_currency,
        exchangeRates=exchange_rates_gql,
        requiredAmenityCount=required_amenity_count,
        venues=venues,
        badges=ComparisonBadgesType(
            bestValue=best_value_rfv,
            bestMatch=best_match_rfv,
        ),
    )


def rfp_pre_send_summary_query(rfpId: str, info: Info) -> PreSendSummaryType:
    user, org_id = _get_user_org(info)
    db = info.context.db

    rfp = crud_rfp.get(db, rfpId)
    if not rfp or rfp.organization_id != org_id:
        raise HTTPException(status_code=404, detail="RFP not found")

    raw_venues = crud_rfp_venue.get_pre_send_summary(db, rfp=rfp)

    fit_items = [
        PreSendVenueFitType(
            venueId=v["venue_id"],
            venueName=v["venue_name"],
            venueCapacity=v["venue_capacity"],
            capacityFit=v["capacity_fit"],
            capacityFitColor=v["capacity_fit_color"],
            amenityMatchPct=v["amenity_match_pct"],
            amenityMatchColor=v["amenity_match_color"],
            matchedAmenities=v["matched_amenities"],
            missingAmenities=v["missing_amenities"],
            priceIndicator=v["price_indicator"],
            priceIndicatorDetail=v.get("price_indicator_detail"),
        )
        for v in raw_venues
    ]

    return PreSendSummaryType(
        rfpId=rfp.id,
        venueCount=len(fit_items),
        venues=fit_items,
    )


def venue_rfp_inbox_query(
    venueId: str,
    info: Info,
    status: Optional[str] = None,
    page: int = 1,
    pageSize: int = 10,
) -> VenueRFPInboxResultType:
    """Venue owner's RFP inbox."""
    user, org_id = _get_user_org(info)
    db = info.context.db

    from ..models.venue import Venue
    venue = db.query(Venue).filter(Venue.id == venueId).first()
    if not venue or venue.organization_id != org_id:
        raise HTTPException(status_code=403, detail="Not authorized")

    import math
    from sqlalchemy.orm import joinedload

    query = (
        db.query(RFPVenue)
        .options(joinedload(RFPVenue.rfp))
        .filter(RFPVenue.venue_id == venueId)
    )
    if status:
        query = query.filter(RFPVenue.status == status)

    total_count = query.count()
    page_size = min(pageSize, 50)
    total_pages = math.ceil(total_count / page_size) if page_size > 0 else 0

    rfp_venues = query.order_by(RFPVenue.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()

    items = []
    for rv in rfp_venues:
        rfp = rv.rfp
        if not rfp:
            continue

        attendance_range = f"{rfp.attendance_min}-{rfp.attendance_max}"
        if rfp.preferred_dates_start and rfp.preferred_dates_end:
            preferred_dates = f"{rfp.preferred_dates_start.strftime('%b %d')}-{rfp.preferred_dates_end.strftime('%d, %Y')}"
        elif rfp.preferred_dates_start:
            preferred_dates = rfp.preferred_dates_start.strftime("%b %d, %Y")
        else:
            preferred_dates = "Flexible"

        items.append(VenueRFPInboxItemType(
            rfvId=rv.id,
            rfpId=rfp.id,
            title=rfp.title,
            eventType=rfp.event_type,
            organizerName=rfp.organization_id,
            attendanceRange=attendance_range,
            preferredDates=preferred_dates,
            status=rv.status,
            responseDeadline=rfp.response_deadline,
            receivedAt=rv.notified_at or rv.created_at,
        ))

    return VenueRFPInboxResultType(
        rfps=items,
        totalCount=total_count,
        page=page,
        pageSize=page_size,
        totalPages=total_pages,
    )


def venue_rfp_detail_query(venueId: str, rfpId: str, info: Info) -> Optional[VenueRFPDetailType]:
    """Venue owner's RFP detail (marks as viewed)."""
    user, org_id = _get_user_org(info)
    db = info.context.db

    from ..models.venue import Venue
    venue = db.query(Venue).filter(Venue.id == venueId).first()
    if not venue or venue.organization_id != org_id:
        raise HTTPException(status_code=403, detail="Not authorized")

    rfv = crud_rfp_venue.get_rfv_for_venue_rfp(db, venueId, rfpId)
    if not rfv:
        return None

    rfp = rfv.rfp
    rfv = crud_rfp_venue.mark_viewed(db, rfv=rfv)

    # Resolve amenities
    required_amenities = []
    if rfp.required_amenity_ids:
        rows = (
            db.query(Amenity.id, Amenity.name, AmenityCategory.name.label("category"))
            .join(AmenityCategory, AmenityCategory.id == Amenity.category_id)
            .filter(Amenity.id.in_(rfp.required_amenity_ids))
            .all()
        )
        required_amenities = [
            RFPAmenityType(id=a.id, name=a.name, category=a.category) for a in rows
        ]

    # Get venue spaces
    venue_spaces = db.query(VenueSpace).filter(VenueSpace.venue_id == venueId).order_by(VenueSpace.sort_order).all()
    spaces = [
        VenueRFPSpaceType(
            id=s.id,
            name=s.name,
            capacity=s.capacity,
            layoutOptions=s.layout_options or [],
        )
        for s in venue_spaces
    ]

    return VenueRFPDetailType(
        rfvId=rfv.id,
        rfpId=rfp.id,
        title=rfp.title,
        eventType=rfp.event_type,
        attendanceMin=rfp.attendance_min,
        attendanceMax=rfp.attendance_max,
        preferredDatesStart=str(rfp.preferred_dates_start) if rfp.preferred_dates_start else None,
        preferredDatesEnd=str(rfp.preferred_dates_end) if rfp.preferred_dates_end else None,
        datesFlexible=rfp.dates_flexible,
        duration=rfp.duration,
        spaceRequirements=rfp.space_requirements or [],
        requiredAmenities=required_amenities,
        cateringNeeds=rfp.catering_needs,
        additionalNotes=rfp.additional_notes,
        responseDeadline=rfp.response_deadline,
        status=rfv.status,
        venueSpaces=spaces,
        existingResponse=_response_to_gql(rfv.response),
    )


def exchange_rates_query(base: str, info: Info, targets: Optional[List[str]] = None) -> ExchangeRateType:
    """Public exchange rates query."""
    from ..utils.exchange_rates import get_exchange_rates_sync

    data = get_exchange_rates_sync(base, targets=targets)
    if not data:
        raise HTTPException(status_code=503, detail="Exchange rates unavailable")

    return ExchangeRateType(
        base=data["base"],
        rates=data["rates"],
        fetchedAt=data["fetched_at"],
    )
