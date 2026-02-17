# app/crud/crud_amenity.py
from typing import Optional, List
from sqlalchemy.orm import Session, joinedload

from app.models.amenity_category import AmenityCategory
from app.models.amenity import Amenity
from app.models.venue_amenity import VenueAmenity
from app.models.venue import Venue


class CRUDAmenity:
    def get_all_categories(self, db: Session) -> List[AmenityCategory]:
        return (
            db.query(AmenityCategory)
            .options(joinedload(AmenityCategory.amenities))
            .order_by(AmenityCategory.sort_order)
            .all()
        )

    def get_amenity(self, db: Session, *, id: str) -> Optional[Amenity]:
        return db.query(Amenity).filter(Amenity.id == id).first()

    def create_category(self, db: Session, *, obj_in: dict) -> AmenityCategory:
        db_obj = AmenityCategory(**obj_in)
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def create_amenity(self, db: Session, *, obj_in: dict) -> Amenity:
        db_obj = Amenity(**obj_in)
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def update_amenity(self, db: Session, *, db_obj: Amenity, obj_in: dict) -> Amenity:
        for field, value in obj_in.items():
            if value is not None:
                setattr(db_obj, field, value)
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def delete_amenity(self, db: Session, *, id: str) -> bool:
        # Check if any venues are using this amenity
        usage_count = db.query(VenueAmenity).filter(
            VenueAmenity.amenity_id == id
        ).count()
        if usage_count > 0:
            return False
        obj = db.query(Amenity).filter(Amenity.id == id).first()
        if not obj:
            return False
        db.delete(obj)
        db.commit()
        return True

    def set_venue_amenities(
        self, db: Session, *, venue_id: str, amenity_items: list
    ) -> List[dict]:
        """Idempotent set: delete all, insert new, return resolved names."""
        # H-02: Lock parent venue row to prevent concurrent duplicate inserts
        db.query(Venue).filter(Venue.id == venue_id).with_for_update().first()

        # Delete existing
        db.query(VenueAmenity).filter(VenueAmenity.venue_id == venue_id).delete()

        # Insert new
        for item in amenity_items:
            va = VenueAmenity(
                venue_id=venue_id,
                amenity_id=item["amenity_id"],
                extra_metadata=item.get("metadata"),
            )
            db.add(va)
        db.commit()

        # Return resolved with names
        rows = (
            db.query(VenueAmenity, Amenity, AmenityCategory)
            .join(Amenity, Amenity.id == VenueAmenity.amenity_id)
            .join(AmenityCategory, AmenityCategory.id == Amenity.category_id)
            .filter(VenueAmenity.venue_id == venue_id)
            .all()
        )

        return [
            {
                "amenity_id": va.amenity_id,
                "name": amenity.name,
                "category_name": category.name,
                "category_icon": category.icon,
                "metadata": va.extra_metadata,
            }
            for va, amenity, category in rows
        ]


amenity = CRUDAmenity()
