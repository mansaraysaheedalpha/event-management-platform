# app/graphql/venue_queries.py
"""GraphQL venue sourcing queries — resolved by VenueQueries mixin class."""
import math
from typing import Optional, List
from strawberry.types import Info
from fastapi import HTTPException

from .. import crud
from ..crud.crud_venue import venue as crud_venue_obj
from ..crud.crud_amenity import amenity as crud_amenity_obj
from .venue_types import (
    VenueFullType,
    VenueDirectoryResultGQL,
    AmenityCategoryTypeGQL,
    AmenityTypeGQL,
    CountryCountGQL,
    CityCountGQL,
    VenueSpaceType,
    VenueSpacePricingType,
    VenuePhotoType,
    VenueAmenityType,
    VenueVerificationDocType,
    VenueListedByType,
    VenuePriceType,
    VenueOwnerStatsType,
)


def _venue_model_to_gql(venue, *, include_relations=False, include_verification=False) -> VenueFullType:
    """Convert a Venue ORM model to VenueFullType."""
    cover_photo_url = None
    spaces = []
    photos = []
    amenities_list = []
    verification_docs = []
    space_count = 0
    min_price = None
    amenity_highlights = []
    listed_by = None

    # L-06: Process photos first so space photos can be populated
    if include_relations and hasattr(venue, "photos"):
        for p in sorted(venue.photos or [], key=lambda x: x.sort_order):
            if p.is_cover:
                cover_photo_url = p.url
            photos.append(
                VenuePhotoType(
                    id=p.id,
                    venueId=p.venue_id,
                    spaceId=p.space_id,
                    url=p.url,
                    category=p.category,
                    caption=p.caption,
                    sortOrder=p.sort_order,
                    isCover=p.is_cover,
                    createdAt=p.created_at,
                )
            )

    if include_relations and hasattr(venue, "spaces"):
        space_count = len(venue.spaces) if venue.spaces else 0
        for s in sorted(venue.spaces or [], key=lambda x: x.sort_order):
            pricing = [
                VenueSpacePricingType(
                    id=p.id,
                    spaceId=p.space_id,
                    rateType=p.rate_type,
                    amount=float(p.amount),
                    currency=p.currency,
                )
                for p in (s.pricing or [])
            ]
            # Track min price
            for p in s.pricing or []:
                if p.rate_type == "full_day":
                    if min_price is None or float(p.amount) < min_price.amount:
                        min_price = VenuePriceType(
                            amount=float(p.amount),
                            currency=p.currency,
                            rateType=p.rate_type,
                        )
            # L-06: Populate space photos from venue.photos filtered by space_id
            space_photos = [
                VenuePhotoType(
                    id=p.id,
                    venueId=p.venue_id,
                    spaceId=p.space_id,
                    url=p.url,
                    category=p.category,
                    caption=p.caption,
                    sortOrder=p.sort_order,
                    isCover=p.is_cover,
                    createdAt=p.created_at,
                )
                for p in sorted(venue.photos or [], key=lambda x: x.sort_order)
                if p.space_id == s.id
            ]
            spaces.append(
                VenueSpaceType(
                    id=s.id,
                    venueId=s.venue_id,
                    name=s.name,
                    description=s.description,
                    capacity=s.capacity,
                    floorLevel=s.floor_level,
                    layoutOptions=s.layout_options or [],
                    sortOrder=s.sort_order,
                    pricing=pricing,
                    photos=space_photos,
                )
            )

    if include_relations and hasattr(venue, "venue_amenities"):
        for va in venue.venue_amenities or []:
            amenity = va.amenity
            category = amenity.category
            amenities_list.append(
                VenueAmenityType(
                    amenityId=amenity.id,
                    name=amenity.name,
                    categoryName=category.name,
                    categoryIcon=category.icon,
                    metadata=va.extra_metadata,
                )
            )
            if len(amenity_highlights) < 4:
                amenity_highlights.append(amenity.name)

    if include_verification and hasattr(venue, "verification_documents"):
        for doc in venue.verification_documents or []:
            verification_docs.append(
                VenueVerificationDocType(
                    id=doc.id,
                    documentType=doc.document_type,
                    filename=doc.filename,
                    url=doc.url,
                    status=doc.status,
                    adminNotes=doc.admin_notes,
                    createdAt=doc.created_at,
                )
            )

    if include_relations and hasattr(venue, "organization") and venue.organization:
        org = venue.organization
        listed_by = VenueListedByType(
            name=org.name,
            email=getattr(org, "email", None),
            memberSince=org.created_at,
        )

    return VenueFullType(
        id=venue.id,
        slug=venue.slug,
        organizationId=venue.organization_id,
        name=venue.name,
        description=venue.description,
        address=venue.address,
        city=venue.city,
        country=venue.country,
        latitude=venue.latitude,
        longitude=venue.longitude,
        website=venue.website,
        phone=venue.phone,
        email=venue.email,
        whatsapp=venue.whatsapp,
        totalCapacity=venue.total_capacity,
        coverPhotoUrl=cover_photo_url,
        isPublic=venue.is_public,
        status=venue.status,
        rejectionReason=venue.rejection_reason,
        verified=venue.verified,
        domainMatch=venue.domain_match,
        availabilityStatus=venue.availability_status,
        submittedAt=venue.submitted_at,
        approvedAt=venue.approved_at,
        isArchived=venue.is_archived,
        createdAt=venue.created_at,
        updatedAt=venue.updated_at,
        spaces=spaces,
        photos=photos,
        amenities=amenities_list,
        verificationDocuments=verification_docs,
        spaceCount=space_count,
        minPrice=min_price,
        amenityHighlights=amenity_highlights,
        listedBy=listed_by,
    )


def venue_directory_query(
    info: Info,
    q: Optional[str] = None,
    country: Optional[str] = None,
    city: Optional[str] = None,
    lat: Optional[float] = None,
    lng: Optional[float] = None,
    radiusKm: Optional[float] = None,
    minCapacity: Optional[int] = None,
    maxPrice: Optional[float] = None,
    currency: Optional[str] = None,
    amenityIds: Optional[List[str]] = None,
    sort: Optional[str] = None,
    page: Optional[int] = None,
    pageSize: Optional[int] = None,
) -> VenueDirectoryResultGQL:
    """Public directory search."""
    db = info.context.db
    result = crud_venue_obj.search_directory(
        db,
        q=q,
        country=country,
        city=city,
        lat=lat,
        lng=lng,
        radius_km=radiusKm or 10,
        min_capacity=minCapacity,
        max_price=maxPrice,
        currency=currency or "USD",
        amenity_ids=amenityIds,
        sort=sort or "recommended",
        page=page or 1,
        page_size=pageSize or 12,
    )

    # Convert dict items to VenueFullType
    venues = []
    for v in result["venues"]:
        min_price = None
        if v.get("min_price"):
            min_price = VenuePriceType(**v["min_price"])
        venues.append(
            VenueFullType(
                id=v["id"],
                slug=v["slug"],
                organizationId="",
                name=v["name"],
                city=v.get("city"),
                country=v.get("country"),
                address=v.get("address"),
                latitude=v.get("latitude"),
                longitude=v.get("longitude"),
                totalCapacity=v.get("total_capacity"),
                verified=v.get("verified", False),
                coverPhotoUrl=v.get("cover_photo_url"),
                spaceCount=v.get("space_count", 0),
                minPrice=min_price,
                amenityHighlights=v.get("amenity_highlights", []),
                createdAt=v.get("created_at"),
            )
        )

    pagination = result["pagination"]
    return VenueDirectoryResultGQL(
        venues=venues,
        totalCount=pagination["total_count"],
        page=pagination["page"],
        pageSize=pagination["page_size"],
        totalPages=pagination["total_pages"],
    )


def venue_by_slug_query(slug: str, info: Info) -> Optional[VenueFullType]:
    """Public venue detail by slug."""
    db = info.context.db
    venue = crud_venue_obj.get_by_slug(db, slug=slug)
    if not venue:
        return None
    return _venue_model_to_gql(venue, include_relations=True)


def venue_amenity_categories_query(info: Info) -> List[AmenityCategoryTypeGQL]:
    """List all amenity categories with amenities."""
    db = info.context.db
    categories = crud_amenity_obj.get_all_categories(db)
    return [
        AmenityCategoryTypeGQL(
            id=cat.id,
            name=cat.name,
            icon=cat.icon,
            sortOrder=cat.sort_order,
            amenities=[
                AmenityTypeGQL(
                    id=a.id,
                    categoryId=a.category_id,
                    name=a.name,
                    icon=a.icon,
                    sortOrder=a.sort_order,
                )
                for a in (cat.amenities or [])
            ],
        )
        for cat in categories
    ]


def venue_countries_query(info: Info) -> List[CountryCountGQL]:
    """List countries with approved venues."""
    db = info.context.db
    countries = crud_venue_obj.get_countries_with_venues(db)
    return [
        CountryCountGQL(code=c["code"], name=c["name"], venueCount=c["venue_count"])
        for c in countries
    ]


def venue_cities_query(info: Info, country: Optional[str] = None) -> List[CityCountGQL]:
    """List cities with approved venues."""
    db = info.context.db
    cities = crud_venue_obj.get_cities_with_venues(db, country=country)
    return [
        CityCountGQL(name=c["name"], country=c["country"], venueCount=c["venue_count"])
        for c in cities
    ]


def organization_venues_query(
    info: Info, status: Optional[str] = None
) -> List[VenueFullType]:
    """List org's venues (authenticated)."""
    user = info.context.user
    if not user or not user.get("orgId"):
        raise HTTPException(status_code=403, detail="Not authorized")
    db = info.context.db
    org_id = user["orgId"]
    venues = crud_venue_obj.get_multi_by_organization(db, org_id=org_id, status=status)
    return [_venue_model_to_gql(v, include_relations=True) for v in venues]


def venue_detail_query(id: str, info: Info) -> Optional[VenueFullType]:
    """Get single venue by ID (owner view with full relations)."""
    user = info.context.user
    if not user or not user.get("orgId"):
        raise HTTPException(status_code=403, detail="Not authorized")
    db = info.context.db
    org_id = user["orgId"]
    venue = crud_venue_obj.get_with_relations(db, id=id)
    if not venue or venue.organization_id != org_id:
        return None
    return _venue_model_to_gql(venue, include_relations=True, include_verification=True)


def admin_venue_queue_query(
    info: Info,
    status: Optional[str] = None,
    domainMatch: Optional[bool] = None,
    page: Optional[int] = None,
    pageSize: Optional[int] = None,
) -> VenueDirectoryResultGQL:
    """Admin venue review queue."""
    user = info.context.user
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")
    role = user.get("role", "")
    if role.lower() not in ("admin", "superadmin"):
        raise HTTPException(status_code=403, detail="Admin access required")

    db = info.context.db
    result = crud_venue_obj.get_admin_venues(
        db,
        status=status,
        domain_match=domainMatch,
        page=page or 1,
        page_size=pageSize or 20,
    )
    pagination = result["pagination"]
    venues = [_venue_model_to_gql(v, include_relations=True, include_verification=True) for v in result["venues"]]
    return VenueDirectoryResultGQL(
        venues=venues,
        totalCount=pagination["total_count"],
        page=pagination["page"],
        pageSize=pagination["page_size"],
        totalPages=pagination["total_pages"],
    )


def venue_owner_stats_query(info: Info) -> VenueOwnerStatsType:
    """Get dashboard statistics for venue owner (organization-wide)."""
    user = info.context.user
    if not user or not user.get("orgId"):
        raise HTTPException(status_code=403, detail="Not authorized")

    db = info.context.db
    org_id = user["orgId"]

    # Import models
    from ..models.venue import Venue
    from ..models.rfp_venue import RFPVenue
    from ..models.event import Event
    from ..models.venue_waitlist_entry import VenueWaitlistEntry
    from sqlalchemy import func

    # Get all venue IDs owned by this organization
    venue_ids = db.query(Venue.id).filter(
        Venue.organization_id == org_id,
        Venue.is_archived == False
    ).all()
    venue_id_list = [v.id for v in venue_ids]

    if not venue_id_list:
        # No venues, return zeros
        return VenueOwnerStatsType(
            pendingRfps=0,
            totalBookings=0,
            waitlistRequests=0
        )

    # 1. Count pending RFPs (received/viewed, not yet responded)
    # RFPVenue statuses: received, viewed, responded, shortlisted, awarded, declined
    pending_rfps = db.query(func.count(RFPVenue.id)).filter(
        RFPVenue.venue_id.in_(venue_id_list),
        RFPVenue.status.in_(["received", "viewed"])
    ).scalar() or 0

    # 2. Count total bookings (events that have a venue_id matching owned venues)
    # Only count confirmed/published events (not draft/cancelled)
    total_bookings = db.query(func.count(Event.id)).filter(
        Event.venue_id.in_(venue_id_list),
        Event.status.in_(["published", "active", "completed"]),
        Event.is_archived == False
    ).scalar() or 0

    # 3. Count active waitlist requests (WAITING or OFFERED status)
    # Status values: waiting, offered, converted, expired, cancelled
    waitlist_requests = db.query(func.count(VenueWaitlistEntry.id)).filter(
        VenueWaitlistEntry.venue_id.in_(venue_id_list),
        VenueWaitlistEntry.status.in_(["waiting", "offered"])
    ).scalar() or 0

    return VenueOwnerStatsType(
        pendingRfps=pending_rfps,
        totalBookings=total_bookings,
        waitlistRequests=waitlist_requests
    )
