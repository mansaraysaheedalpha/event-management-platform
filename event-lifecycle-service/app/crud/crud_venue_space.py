# app/crud/crud_venue_space.py
from typing import Optional, List
from sqlalchemy.orm import Session, joinedload
import logging

from app.models.venue_space import VenueSpace
from app.models.venue_space_pricing import VenueSpacePricing

logger = logging.getLogger(__name__)


class CRUDVenueSpace:
    def create(self, db: Session, *, venue_id: str, obj_in: dict) -> VenueSpace:
        db_obj = VenueSpace(venue_id=venue_id, **obj_in)
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def get(self, db: Session, *, id: str) -> Optional[VenueSpace]:
        return db.query(VenueSpace).filter(VenueSpace.id == id).first()

    def get_multi_by_venue(self, db: Session, *, venue_id: str) -> List[VenueSpace]:
        return (
            db.query(VenueSpace)
            .options(joinedload(VenueSpace.pricing))
            .filter(VenueSpace.venue_id == venue_id)
            .order_by(VenueSpace.sort_order)
            .all()
        )

    def update(self, db: Session, *, db_obj: VenueSpace, obj_in: dict) -> VenueSpace:
        for field, value in obj_in.items():
            if value is not None:
                setattr(db_obj, field, value)
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def delete(self, db: Session, *, id: str) -> bool:
        obj = db.query(VenueSpace).filter(VenueSpace.id == id).first()
        if not obj:
            return False
        db.delete(obj)
        db.commit()
        return True

    def set_pricing(
        self, db: Session, *, space_id: str, pricing_items: list
    ) -> List[VenueSpacePricing]:
        # H-02: Lock parent row to prevent concurrent duplicate inserts
        db.query(VenueSpace).filter(
            VenueSpace.id == space_id
        ).with_for_update().first()

        # Delete existing pricing
        db.query(VenueSpacePricing).filter(
            VenueSpacePricing.space_id == space_id
        ).delete()

        # Insert new pricing
        new_pricing = []
        for item in pricing_items:
            pricing = VenueSpacePricing(
                space_id=space_id,
                rate_type=item["rate_type"],
                amount=item["amount"],
                currency=item["currency"],
            )
            db.add(pricing)
            new_pricing.append(pricing)

        db.commit()
        for p in new_pricing:
            db.refresh(p)
        return new_pricing


venue_space = CRUDVenueSpace()
