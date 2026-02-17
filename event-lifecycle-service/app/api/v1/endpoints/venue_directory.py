# app/api/v1/endpoints/venue_directory.py
import json
import httpx
import logging
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.core.limiter import limiter
from app.core.config import settings
from app.db.session import get_db
from app.crud.crud_venue import venue as crud_venue_obj
from app.crud.crud_amenity import amenity as crud_amenity_obj
from app.schemas.venue import (
    VenueDirectoryResult,
    VenueDirectoryDetail,
    VenuePhotoResponse,
    VenueSpaceResponse,
    VenueSpacePricingResponse,
    VenueAmenityResponse,
    VenueListedBy,
    CountryCount,
    CityCount,
)
from app.schemas.amenity import AmenityCategoryResponse

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Venue Directory"])

CACHE_TTL_SECONDS = 300  # 5 minutes


def _cache_get(key: str) -> Optional[dict]:
    """Try to read from Redis cache. Returns None on miss or error."""
    try:
        from app.db.redis import redis_client
        raw = redis_client.get(key)
        if raw:
            return json.loads(raw)
    except Exception:
        pass
    return None


def _cache_set(key: str, data, ttl: int = CACHE_TTL_SECONDS):
    """Best-effort write to Redis cache."""
    try:
        from app.db.redis import redis_client
        redis_client.setex(key, ttl, json.dumps(data, default=str))
    except Exception:
        pass


def _resolve_org_name(org_id: str) -> Optional[str]:
    """H-07: Fetch organization name from user-and-org-service."""
    if not settings.USER_SERVICE_URL:
        return None
    try:
        resp = httpx.get(
            f"{settings.USER_SERVICE_URL}/api/organizations/{org_id}",
            timeout=3.0,
        )
        if resp.status_code == 200:
            data = resp.json()
            return data.get("name") or data.get("organizationName")
    except Exception:
        logger.debug("Failed to resolve org name for %s", org_id)
    return None


@router.get("/venues/directory", response_model=VenueDirectoryResult)
@limiter.limit("60/minute")
def search_venues(
    request: Request,
    q: Optional[str] = None,
    country: Optional[str] = None,
    city: Optional[str] = None,
    lat: Optional[float] = None,
    lng: Optional[float] = None,
    radius_km: Optional[float] = Query(default=10),
    min_capacity: Optional[int] = None,
    max_price: Optional[float] = None,
    currency: Optional[str] = Query(default="USD"),
    amenities: Optional[str] = None,
    sort: Optional[str] = Query(default="recommended"),
    page: Optional[int] = Query(default=1, ge=1),
    page_size: Optional[int] = Query(default=12, ge=1, le=48),
    db: Session = Depends(get_db),
):
    """Search and browse the public venue directory."""
    amenity_ids = None
    if amenities:
        amenity_ids = [a.strip() for a in amenities.split(",") if a.strip()][:20]

    result = crud_venue_obj.search_directory(
        db,
        q=q,
        country=country,
        city=city,
        lat=lat,
        lng=lng,
        radius_km=radius_km or 10,
        min_capacity=min_capacity,
        max_price=max_price,
        currency=currency or "USD",
        amenity_ids=amenity_ids,
        sort=sort or "recommended",
        page=page or 1,
        page_size=page_size or 12,
    )
    return result


@router.get("/venues/directory/{slug}", response_model=VenueDirectoryDetail)
@limiter.limit("60/minute")
def get_venue_by_slug(
    slug: str,
    request: Request,
    db: Session = Depends(get_db),
):
    """Get a single venue's full public profile by slug."""
    venue = crud_venue_obj.get_by_slug(db, slug=slug)
    if not venue:
        raise HTTPException(status_code=404, detail="Venue not found")

    # Build cover_photo_url
    cover_photo_url = None
    for photo in venue.photos:
        if photo.is_cover:
            cover_photo_url = photo.url
            break

    # Build photos
    photos = [
        VenuePhotoResponse(
            id=p.id,
            url=p.url,
            category=p.category,
            caption=p.caption,
            is_cover=p.is_cover,
            sort_order=p.sort_order,
        )
        for p in sorted(venue.photos, key=lambda x: x.sort_order)
    ]

    # Build spaces with pricing and photos
    spaces = []
    for space in sorted(venue.spaces, key=lambda x: x.sort_order):
        pricing = [
            VenueSpacePricingResponse(
                rate_type=pr.rate_type,
                amount=float(pr.amount),
                currency=pr.currency,
            )
            for pr in space.pricing
        ]
        spaces.append(
            VenueSpaceResponse(
                id=space.id,
                name=space.name,
                description=space.description,
                capacity=space.capacity,
                floor_level=space.floor_level,
                layout_options=space.layout_options or [],
                pricing=pricing,
                photos=[
                    VenuePhotoResponse(
                        id=p.id,
                        url=p.url,
                        category=p.category,
                        caption=p.caption,
                        is_cover=p.is_cover,
                        sort_order=p.sort_order,
                    )
                    for p in venue.photos
                    if p.space_id == space.id
                ],
            )
        )

    # Build amenities
    amenities_list = []
    for va in venue.venue_amenities:
        amenity = va.amenity
        category = amenity.category
        amenities_list.append(
            VenueAmenityResponse(
                id=amenity.id,
                name=amenity.name,
                category=category.name,
                category_icon=category.icon,
                metadata=va.extra_metadata,
            )
        )

    # H-07: Resolve org name instead of exposing raw org_id
    org_name = _resolve_org_name(venue.organization_id) or "Venue Host"

    return VenueDirectoryDetail(
        id=venue.id,
        slug=venue.slug,
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
        total_capacity=venue.total_capacity,
        verified=venue.verified,
        cover_photo_url=cover_photo_url,
        photos=photos,
        spaces=spaces,
        amenities=amenities_list,
        listed_by=VenueListedBy(
            name=org_name,
            member_since=venue.created_at,
        ),
        created_at=venue.created_at,
        updated_at=venue.updated_at,
    )


@router.get("/venues/amenities")
@limiter.limit("60/minute")
def list_amenity_categories(
    request: Request,
    db: Session = Depends(get_db),
):
    """List all amenity categories and their amenities (for building filter UI)."""
    cached = _cache_get("venue:amenities")
    if cached:
        return JSONResponse(content=cached)
    categories = crud_amenity_obj.get_all_categories(db)
    result = {
        "categories": [
            AmenityCategoryResponse.model_validate(cat).model_dump() for cat in categories
        ]
    }
    _cache_set("venue:amenities", result)
    return result


@router.get("/venues/countries")
@limiter.limit("60/minute")
def list_countries(
    request: Request,
    db: Session = Depends(get_db),
):
    """List countries that have at least one approved venue."""
    cached = _cache_get("venue:countries")
    if cached:
        return JSONResponse(content=cached)
    countries = crud_venue_obj.get_countries_with_venues(db)
    result = {"countries": countries}
    _cache_set("venue:countries", result)
    return result


@router.get("/venues/cities")
@limiter.limit("60/minute")
def list_cities(
    request: Request,
    country: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """List cities with approved venues, optionally filtered by country."""
    cache_key = f"venue:cities:{country or 'all'}"
    cached = _cache_get(cache_key)
    if cached:
        return JSONResponse(content=cached)
    cities = crud_venue_obj.get_cities_with_venues(db, country=country)
    result = {"cities": cities}
    _cache_set(cache_key, result)
    return result
