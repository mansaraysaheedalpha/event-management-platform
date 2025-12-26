# app/crud/crud_promo_code.py
from typing import List, Optional
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_

from app.crud.base import CRUDBase
from app.models.promo_code import PromoCode
from app.schemas.payment import PromoCodeCreate, PromoCodeUpdate


class CRUDPromoCode(CRUDBase[PromoCode, PromoCodeCreate, PromoCodeUpdate]):
    """CRUD operations for PromoCode model."""

    def get_by_code(
        self,
        db: Session,
        *,
        organization_id: str,
        code: str,
        event_id: Optional[str] = None,
    ) -> Optional[PromoCode]:
        """Get a promo code by its code string."""
        query = db.query(self.model).filter(
            and_(
                self.model.organization_id == organization_id,
                self.model.code == code.upper(),
            )
        )

        if event_id:
            # Get codes that are either global or specific to this event
            query = query.filter(
                or_(
                    self.model.event_id == None,
                    self.model.event_id == event_id,
                )
            )

        return query.first()

    def get_valid_promo_code(
        self,
        db: Session,
        *,
        organization_id: str,
        code: str,
        event_id: Optional[str] = None,
    ) -> Optional[PromoCode]:
        """Get a promo code if it's valid for use."""
        promo = self.get_by_code(
            db, organization_id=organization_id, code=code, event_id=event_id
        )

        if not promo:
            return None

        if not promo.is_valid:
            return None

        return promo

    def get_by_organization(
        self,
        db: Session,
        *,
        organization_id: str,
        include_inactive: bool = False,
    ) -> List[PromoCode]:
        """Get all promo codes for an organization."""
        query = db.query(self.model).filter(
            self.model.organization_id == organization_id
        )

        if not include_inactive:
            query = query.filter(self.model.is_active == True)

        return query.order_by(self.model.created_at.desc()).all()

    def get_by_event(
        self,
        db: Session,
        *,
        event_id: str,
        include_inactive: bool = False,
    ) -> List[PromoCode]:
        """Get all promo codes for a specific event."""
        query = db.query(self.model).filter(self.model.event_id == event_id)

        if not include_inactive:
            query = query.filter(self.model.is_active == True)

        return query.order_by(self.model.created_at.desc()).all()

    def create_for_organization(
        self, db: Session, *, obj_in: PromoCodeCreate, organization_id: str
    ) -> PromoCode:
        """Create a new promo code for an organization."""
        db_obj = PromoCode(
            organization_id=organization_id,
            event_id=obj_in.event_id,
            code=obj_in.code.upper(),
            description=obj_in.description,
            discount_type=obj_in.discount_type.value,
            discount_value=obj_in.discount_value,
            currency=obj_in.currency,
            applicable_ticket_type_ids=obj_in.applicable_ticket_type_ids,
            max_uses=obj_in.max_uses,
            max_uses_per_user=obj_in.max_uses_per_user,
            minimum_order_amount=obj_in.minimum_order_amount,
            minimum_tickets=obj_in.minimum_tickets,
            min_order_amount=obj_in.min_order_amount,  # Legacy
            max_discount_amount=obj_in.max_discount_amount,
            valid_from=obj_in.valid_from,
            valid_until=obj_in.valid_until,
            is_active=obj_in.is_active,
        )
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def increment_usage(
        self, db: Session, *, promo_code_id: str
    ) -> Optional[PromoCode]:
        """Increment the usage count for a promo code."""
        promo = self.get(db, id=promo_code_id)
        if not promo:
            return None

        promo.times_used += 1
        promo.updated_at = datetime.now(timezone.utc)
        db.add(promo)
        db.commit()
        db.refresh(promo)
        return promo

    def decrement_usage(
        self, db: Session, *, promo_code_id: str
    ) -> Optional[PromoCode]:
        """Decrement the usage count for a promo code (for refunds)."""
        promo = self.get(db, id=promo_code_id)
        if not promo:
            return None

        promo.times_used = max(0, promo.times_used - 1)
        promo.updated_at = datetime.now(timezone.utc)
        db.add(promo)
        db.commit()
        db.refresh(promo)
        return promo

    def validate_for_order(
        self,
        db: Session,
        *,
        promo_code_id: str,
        subtotal: int,
    ) -> tuple[bool, Optional[str]]:
        """Validate a promo code for an order and return discount amount."""
        promo = self.get(db, id=promo_code_id)
        if not promo:
            return False, "Promo code not found"

        if not promo.is_valid:
            if not promo.is_active:
                return False, "Promo code is no longer active"
            if promo.max_uses and promo.times_used >= promo.max_uses:
                return False, "Promo code has reached maximum uses"

            now = datetime.now(timezone.utc)
            if promo.valid_from and now < promo.valid_from:
                return False, "Promo code is not yet valid"
            if promo.valid_until and now > promo.valid_until:
                return False, "Promo code has expired"

        if promo.min_order_amount and subtotal < promo.min_order_amount:
            return False, f"Minimum order amount not met"

        return True, None


promo_code = CRUDPromoCode(PromoCode)
