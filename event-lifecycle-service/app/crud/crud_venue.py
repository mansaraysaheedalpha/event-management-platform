#app/crud/crud_venue.py
import math
from math import cos, radians
from typing import Optional, List
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, or_
from datetime import datetime, timezone

from typing import Union, Dict, Any
from .base import CRUDBase
from app.models.venue import Venue
from app.models.venue_space import VenueSpace
from app.models.venue_space_pricing import VenueSpacePricing
from app.models.venue_photo import VenuePhoto
from app.models.venue_amenity import VenueAmenity
from app.models.amenity import Amenity
from app.schemas.venue import VenueCreate, VenueUpdate
from app.utils.slug import generate_slug

# Fields that require re-review if changed on an approved venue
_TRUST_CRITICAL_FIELDS = {"name", "address", "city", "country"}

# ISO 3166-1 alpha-2 country code to name mapping
COUNTRY_NAMES = {
    "KE": "Kenya", "NG": "Nigeria", "ZA": "South Africa", "GH": "Ghana",
    "TZ": "Tanzania", "UG": "Uganda", "RW": "Rwanda", "ET": "Ethiopia",
    "EG": "Egypt", "MA": "Morocco", "SN": "Senegal", "CI": "Ivory Coast",
    "CM": "Cameroon", "AO": "Angola", "MZ": "Mozambique", "ZW": "Zimbabwe",
    "BW": "Botswana", "NA": "Namibia", "MU": "Mauritius",
    "US": "United States", "GB": "United Kingdom", "CA": "Canada",
    "AU": "Australia", "DE": "Germany", "FR": "France", "AE": "UAE",
    "IN": "India", "JP": "Japan", "BR": "Brazil", "MX": "Mexico",
}


class CRUDVenue(CRUDBase[Venue, VenueCreate, VenueUpdate]):

    def create_with_organization(
        self, db: Session, *, obj_in: VenueCreate, org_id: str
    ) -> Venue:
        obj_data = obj_in.model_dump()
        slug = generate_slug(obj_data["name"], db)
        db_obj = Venue(
            **obj_data,
            organization_id=org_id,
            slug=slug,
            status="draft",
            is_archived=False,
        )
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def update(
        self,
        db: Session,
        *,
        db_obj: Venue,
        obj_in: Union[VenueUpdate, Dict[str, Any]],
    ) -> Venue:
        if isinstance(obj_in, dict):
            update_data = obj_in
        else:
            update_data = obj_in.model_dump(exclude_unset=True)

        # L-01: Regenerate slug if name changed
        if "name" in update_data and update_data["name"] != db_obj.name:
            update_data["slug"] = generate_slug(update_data["name"], db)

        # H-09: If venue is approved and trust-critical fields changed, require re-review
        if db_obj.status == "approved":
            changed_critical = _TRUST_CRITICAL_FIELDS & set(update_data.keys())
            actually_changed = {
                f for f in changed_critical
                if update_data[f] != getattr(db_obj, f)
            }
            if actually_changed:
                update_data["status"] = "pending_review"
                update_data["verified"] = False

        for field, value in update_data.items():
            setattr(db_obj, field, value)
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def recompute_total_capacity(self, db: Session, *, venue_id: str) -> None:
        """L-02: Recompute venue.total_capacity from max(space.capacity)."""
        result = (
            db.query(func.max(VenueSpace.capacity))
            .filter(VenueSpace.venue_id == venue_id)
            .scalar()
        )
        db.query(Venue).filter(Venue.id == venue_id).update(
            {"total_capacity": result}
        )
        db.commit()

    def get_by_slug(self, db: Session, *, slug: str) -> Optional[Venue]:
        return (
            db.query(Venue)
            .options(
                joinedload(Venue.spaces).joinedload(VenueSpace.pricing),
                joinedload(Venue.photos),
                joinedload(Venue.venue_amenities).joinedload(VenueAmenity.amenity).joinedload(Amenity.category),
            )
            .filter(Venue.slug == slug, Venue.status == "approved", Venue.is_public == True, Venue.is_archived == False)
            .first()
        )

    def get_with_relations(self, db: Session, *, id: str) -> Optional[Venue]:
        """Get venue with all nested relations loaded (for owner view)."""
        return (
            db.query(Venue)
            .options(
                joinedload(Venue.spaces).joinedload(VenueSpace.pricing),
                joinedload(Venue.photos),
                joinedload(Venue.venue_amenities).joinedload(VenueAmenity.amenity).joinedload(Amenity.category),
                joinedload(Venue.verification_documents),
            )
            .filter(Venue.id == id)
            .first()
        )

    def get_multi_by_organization(
        self, db: Session, *, org_id: str, status: str = None, skip: int = 0, limit: int = 100
    ) -> List[Venue]:
        query = (
            db.query(Venue)
            .options(
                joinedload(Venue.spaces).joinedload(VenueSpace.pricing),
                joinedload(Venue.photos),
                joinedload(Venue.venue_amenities).joinedload(VenueAmenity.amenity).joinedload(Amenity.category),
            )
            .filter(
                Venue.organization_id == org_id,
                Venue.is_archived == False,
            )
        )
        if status:
            query = query.filter(Venue.status == status)
        return query.order_by(Venue.created_at.desc()).offset(skip).limit(limit).all()

    def search_directory(
        self,
        db: Session,
        *,
        q: str = None,
        country: str = None,
        city: str = None,
        lat: float = None,
        lng: float = None,
        radius_km: float = 10,
        min_capacity: int = None,
        max_price: float = None,
        currency: str = "USD",
        amenity_ids: List[str] = None,
        sort: str = "recommended",
        page: int = 1,
        page_size: int = 12,
    ) -> dict:
        """Main directory search with all filters, pagination, and geo-search."""
        page_size = min(page_size, 48)
        offset = (page - 1) * page_size

        query = db.query(Venue).filter(
            Venue.status == "approved",
            Venue.is_public == True,
            Venue.is_archived == False,
        )

        # Text search (H-04: escape LIKE wildcards)
        if q:
            q_escaped = q.replace("\\", "\\\\").replace("%", r"\%").replace("_", r"\_")
            search_term = f"%{q_escaped}%"
            query = query.filter(
                or_(
                    Venue.name.ilike(search_term),
                    Venue.city.ilike(search_term),
                    Venue.address.ilike(search_term),
                )
            )

        # Country filter
        if country:
            query = query.filter(Venue.country == country.upper())

        # City filter
        if city:
            city_escaped = city.replace("\\", "\\\\").replace("%", r"\%").replace("_", r"\_")
            query = query.filter(Venue.city.ilike(f"%{city_escaped}%"))

        # Capacity filter
        if min_capacity:
            query = query.filter(Venue.total_capacity >= min_capacity)

        # Amenity filter (AND — venue must have ALL selected amenities)
        if amenity_ids:
            for amenity_id in amenity_ids:
                query = query.filter(
                    Venue.id.in_(
                        db.query(VenueAmenity.venue_id).filter(
                            VenueAmenity.amenity_id == amenity_id
                        )
                    )
                )

        # Price filter (max full-day rate)
        if max_price is not None:
            subq = (
                db.query(VenueSpace.venue_id)
                .join(VenueSpacePricing, VenueSpacePricing.space_id == VenueSpace.id)
                .filter(
                    VenueSpacePricing.rate_type == "full_day",
                    VenueSpacePricing.amount <= max_price,
                    VenueSpacePricing.currency == currency,
                )
                .subquery()
            )
            query = query.filter(Venue.id.in_(db.query(subq.c.venue_id)))

        # Geo-search (Haversine formula with H-08 bounding-box pre-filter)
        if lat is not None and lng is not None:
            # Bounding box pre-filter to reduce candidate set before trig
            lat_delta = radius_km / 111.0
            lng_delta = radius_km / (111.0 * max(cos(radians(lat)), 0.01))
            query = query.filter(
                Venue.latitude.isnot(None),
                Venue.longitude.isnot(None),
                Venue.latitude.between(lat - lat_delta, lat + lat_delta),
                Venue.longitude.between(lng - lng_delta, lng + lng_delta),
            )

            haversine = (
                6371
                * func.acos(
                    func.least(
                        1.0,
                        func.sin(func.radians(lat)) * func.sin(func.radians(Venue.latitude))
                        + func.cos(func.radians(lat))
                        * func.cos(func.radians(Venue.latitude))
                        * func.cos(func.radians(Venue.longitude) - func.radians(lng)),
                    )
                )
            )
            query = query.filter(haversine <= radius_km)

        # Count total before pagination
        total_count = query.count()
        total_pages = math.ceil(total_count / page_size) if page_size > 0 else 0

        # Sorting
        if sort == "price_asc":
            query = query.outerjoin(VenueSpace, VenueSpace.venue_id == Venue.id).outerjoin(
                VenueSpacePricing, VenueSpacePricing.space_id == VenueSpace.id
            ).group_by(Venue.id).order_by(func.min(VenueSpacePricing.amount).asc().nullslast())
        elif sort == "price_desc":
            query = query.outerjoin(VenueSpace, VenueSpace.venue_id == Venue.id).outerjoin(
                VenueSpacePricing, VenueSpacePricing.space_id == VenueSpace.id
            ).group_by(Venue.id).order_by(func.min(VenueSpacePricing.amount).desc().nullslast())
        elif sort == "capacity_desc":
            query = query.order_by(Venue.total_capacity.desc().nullslast())
        elif sort == "newest":
            query = query.order_by(Venue.created_at.desc())
        else:  # "recommended"
            query = query.order_by(Venue.verified.desc(), Venue.created_at.desc())

        venues = query.offset(offset).limit(page_size).all()

        # Enrich with computed fields in batch
        venue_ids = [v.id for v in venues]

        space_counts = dict(
            db.query(VenueSpace.venue_id, func.count(VenueSpace.id))
            .filter(VenueSpace.venue_id.in_(venue_ids))
            .group_by(VenueSpace.venue_id)
            .all()
        )

        min_prices_rows = (
            db.query(
                VenueSpace.venue_id,
                func.min(VenueSpacePricing.amount).label("min_amount"),
                VenueSpacePricing.currency,
                VenueSpacePricing.rate_type,
            )
            .join(VenueSpacePricing, VenueSpacePricing.space_id == VenueSpace.id)
            .filter(
                VenueSpace.venue_id.in_(venue_ids),
                VenueSpacePricing.rate_type == "full_day",
            )
            .group_by(VenueSpace.venue_id, VenueSpacePricing.currency, VenueSpacePricing.rate_type)
            .all()
        )
        min_prices = {}
        for row in min_prices_rows:
            if row.venue_id not in min_prices or float(row.min_amount) < min_prices[row.venue_id]["amount"]:
                min_prices[row.venue_id] = {
                    "amount": float(row.min_amount),
                    "currency": row.currency,
                    "rate_type": row.rate_type,
                }

        cover_photos = dict(
            db.query(VenuePhoto.venue_id, VenuePhoto.url)
            .filter(VenuePhoto.venue_id.in_(venue_ids), VenuePhoto.is_cover == True)
            .all()
        )

        amenity_rows = (
            db.query(VenueAmenity.venue_id, Amenity.name)
            .join(Amenity, Amenity.id == VenueAmenity.amenity_id)
            .filter(VenueAmenity.venue_id.in_(venue_ids))
            .order_by(Amenity.sort_order)
            .all()
        )
        amenity_highlights = {}
        for row in amenity_rows:
            if row.venue_id not in amenity_highlights:
                amenity_highlights[row.venue_id] = []
            if len(amenity_highlights[row.venue_id]) < 4:
                amenity_highlights[row.venue_id].append(row.name)

        result_venues = []
        for v in venues:
            result_venues.append({
                "id": v.id,
                "slug": v.slug,
                "name": v.name,
                "city": v.city,
                "country": v.country,
                "address": v.address,
                "latitude": v.latitude,
                "longitude": v.longitude,
                "total_capacity": v.total_capacity,
                "verified": v.verified,
                "cover_photo_url": cover_photos.get(v.id),
                "space_count": space_counts.get(v.id, 0),
                "min_price": min_prices.get(v.id),
                "amenity_highlights": amenity_highlights.get(v.id, []),
                "created_at": v.created_at,
            })

        return {
            "venues": result_venues,
            "pagination": {
                "page": page,
                "page_size": page_size,
                "total_count": total_count,
                "total_pages": total_pages,
            },
        }

    def get_countries_with_venues(self, db: Session) -> List[dict]:
        rows = (
            db.query(Venue.country, func.count(Venue.id).label("venue_count"))
            .filter(
                Venue.status == "approved",
                Venue.is_public == True,
                Venue.is_archived == False,
                Venue.country.isnot(None),
            )
            .group_by(Venue.country)
            .order_by(func.count(Venue.id).desc())
            .limit(200)
            .all()
        )
        return [
            {
                "code": row.country,
                "name": COUNTRY_NAMES.get(row.country, row.country),
                "venue_count": row.venue_count,
            }
            for row in rows
        ]

    def get_cities_with_venues(self, db: Session, country: str = None) -> List[dict]:
        query = (
            db.query(Venue.city, Venue.country, func.count(Venue.id).label("venue_count"))
            .filter(
                Venue.status == "approved",
                Venue.is_public == True,
                Venue.is_archived == False,
                Venue.city.isnot(None),
            )
        )
        if country:
            query = query.filter(Venue.country == country.upper())
        rows = (
            query.group_by(Venue.city, Venue.country)
            .order_by(func.count(Venue.id).desc())
            .limit(500)
            .all()
        )
        return [
            {"name": row.city, "country": row.country, "venue_count": row.venue_count}
            for row in rows
        ]

    def submit_for_review(self, db: Session, *, venue_id: str) -> Optional[Venue]:
        venue = db.query(Venue).filter(Venue.id == venue_id).first()
        if not venue:
            return None
        if venue.status not in ("draft", "rejected"):
            raise ValueError(f"Cannot submit venue with status '{venue.status}'")
        venue.status = "pending_review"
        venue.submitted_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(venue)
        return venue

    def approve(self, db: Session, *, venue_id: str) -> Optional[Venue]:
        venue = db.query(Venue).filter(Venue.id == venue_id).first()
        if not venue:
            return None
        if venue.status != "pending_review":
            raise ValueError(f"Cannot approve venue with status '{venue.status}'")
        venue.status = "approved"
        venue.verified = True
        venue.approved_at = datetime.now(timezone.utc)
        venue.rejection_reason = None
        db.commit()
        db.refresh(venue)
        return venue

    def reject(self, db: Session, *, venue_id: str, reason: str) -> Optional[Venue]:
        venue = db.query(Venue).filter(Venue.id == venue_id).first()
        if not venue:
            return None
        if venue.status != "pending_review":
            raise ValueError(f"Cannot reject venue with status '{venue.status}'")
        venue.status = "rejected"
        venue.rejection_reason = reason
        db.commit()
        db.refresh(venue)
        return venue

    def suspend(self, db: Session, *, venue_id: str, reason: str) -> Optional[Venue]:
        venue = db.query(Venue).filter(Venue.id == venue_id).first()
        if not venue:
            return None
        if venue.status != "approved":
            raise ValueError(f"Cannot suspend venue with status '{venue.status}'")
        venue.status = "suspended"
        venue.rejection_reason = reason
        db.commit()
        db.refresh(venue)
        return venue

    def get_admin_venues(
        self, db: Session, *, status: str = None, domain_match: bool = None,
        sort: str = "submitted_at_asc", page: int = 1, page_size: int = 20,
    ) -> dict:
        query = (
            db.query(Venue)
            .options(
                joinedload(Venue.spaces).joinedload(VenueSpace.pricing),
                joinedload(Venue.photos),
                joinedload(Venue.venue_amenities).joinedload(VenueAmenity.amenity).joinedload(Amenity.category),
                joinedload(Venue.verification_documents),
                joinedload(Venue.organization),
            )
            .filter(Venue.is_archived == False)
        )
        if status:
            query = query.filter(Venue.status == status)
        if domain_match is not None:
            query = query.filter(Venue.domain_match == domain_match)

        total_count = query.count()
        total_pages = math.ceil(total_count / page_size) if page_size > 0 else 0

        if sort == "submitted_at_desc":
            query = query.order_by(Venue.submitted_at.desc().nullslast())
        else:
            query = query.order_by(Venue.submitted_at.asc().nullslast())

        offset = (page - 1) * page_size
        venues = query.offset(offset).limit(page_size).all()

        return {
            "venues": venues,
            "pagination": {
                "page": page,
                "page_size": page_size,
                "total_count": total_count,
                "total_pages": total_pages,
            },
        }


venue = CRUDVenue(Venue)
