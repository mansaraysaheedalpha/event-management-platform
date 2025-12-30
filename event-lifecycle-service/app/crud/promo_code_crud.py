# app/crud/promo_code_crud.py
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func
from typing import List, Optional
from datetime import datetime, timezone

from app.models.promo_code import PromoCode
from app.models.promo_code_usage import PromoCodeUsage
from app.schemas.ticket_management import PromoCodeCreate, PromoCodeUpdate


class CRUDPromoCode:
    """CRUD operations for promo codes."""

    def get(self, db: Session, promo_code_id: str) -> Optional[PromoCode]:
        """Get a promo code by ID."""
        return db.query(PromoCode).filter(PromoCode.id == promo_code_id).first()

    def get_by_code(
        self,
        db: Session,
        code: str,
        organization_id: str,
        event_id: Optional[str] = None
    ) -> Optional[PromoCode]:
        """Get a promo code by its code string."""
        code_upper = code.upper()

        # Match event-specific or organization-wide codes
        query = db.query(PromoCode).filter(
            and_(
                PromoCode.organization_id == organization_id,
                func.upper(PromoCode.code) == code_upper,
                or_(
                    PromoCode.event_id == event_id,
                    PromoCode.event_id.is_(None)  # org-wide codes
                )
            )
        )

        return query.first()

    def get_by_event(
        self,
        db: Session,
        event_id: str,
        include_inactive: bool = False
    ) -> List[PromoCode]:
        """Get all promo codes for an event."""
        query = db.query(PromoCode).filter(PromoCode.event_id == event_id)

        if not include_inactive:
            query = query.filter(PromoCode.is_active == True)

        return query.order_by(PromoCode.created_at.desc()).all()

    def get_by_organization(
        self,
        db: Session,
        organization_id: str,
        org_wide_only: bool = False
    ) -> List[PromoCode]:
        """Get all promo codes for an organization."""
        query = db.query(PromoCode).filter(
            PromoCode.organization_id == organization_id
        )

        if org_wide_only:
            query = query.filter(PromoCode.event_id.is_(None))

        return query.order_by(PromoCode.created_at.desc()).all()

    def create(
        self,
        db: Session,
        obj_in: PromoCodeCreate,
        organization_id: str,
        created_by: Optional[str] = None
    ) -> PromoCode:
        """Create a new promo code."""
        db_obj = PromoCode(
            organization_id=organization_id,
            event_id=obj_in.event_id,
            code=obj_in.code.upper(),
            description=obj_in.description,
            discount_type=obj_in.discount_type.value,
            discount_value=obj_in.discount_value,
            applicable_ticket_type_ids=obj_in.applicable_ticket_type_ids,
            max_uses=obj_in.max_uses,
            max_uses_per_user=obj_in.max_uses_per_user,
            valid_from=obj_in.valid_from,
            valid_until=obj_in.valid_until,
            minimum_order_amount=obj_in.minimum_order_amount,
            minimum_tickets=obj_in.minimum_tickets,
            created_by=created_by,
        )
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def update(
        self,
        db: Session,
        promo_code_id: str,
        obj_in: PromoCodeUpdate
    ) -> Optional[PromoCode]:
        """Update a promo code."""
        db_obj = self.get(db, promo_code_id)
        if not db_obj:
            return None

        update_data = obj_in.model_dump(exclude_unset=True)

        # Convert enum to string if present
        if 'discount_type' in update_data and update_data['discount_type']:
            update_data['discount_type'] = update_data['discount_type'].value

        # Handle currency update if present
        if 'currency' in update_data:
            db_obj.currency = update_data['currency']

        update_data['updated_at'] = datetime.now(timezone.utc)

        for field, value in update_data.items():
            setattr(db_obj, field, value)

        db.commit()
        db.refresh(db_obj)
        return db_obj

    def delete(self, db: Session, promo_code_id: str) -> bool:
        """Delete a promo code."""
        db_obj = self.get(db, promo_code_id)
        if not db_obj:
            return False

        db.delete(db_obj)
        db.commit()
        return True

    def deactivate(
        self,
        db: Session,
        promo_code_id: str
    ) -> Optional[PromoCode]:
        """Deactivate a promo code (soft disable)."""
        db_obj = self.get(db, promo_code_id)
        if not db_obj:
            return None

        db_obj.is_active = False
        db_obj.updated_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def increment_usage(
        self,
        db: Session,
        promo_code_id: str,
        count: int = 1
    ) -> bool:
        """Increment the usage count of a promo code."""
        db_obj = self.get(db, promo_code_id)
        if not db_obj:
            return False

        db_obj.current_uses += count
        db_obj.times_used += count  # Legacy column
        db.commit()
        return True

    def get_user_usage_count(
        self,
        db: Session,
        promo_code_id: str,
        user_id: Optional[str] = None,
        guest_email: Optional[str] = None
    ) -> int:
        """Get how many times a user/email has used a promo code."""
        query = db.query(func.count(PromoCodeUsage.id)).filter(
            PromoCodeUsage.promo_code_id == promo_code_id
        )

        if user_id:
            query = query.filter(PromoCodeUsage.user_id == user_id)
        elif guest_email:
            query = query.filter(
                func.lower(PromoCodeUsage.guest_email) == guest_email.lower()
            )
        else:
            return 0

        return query.scalar() or 0

    def record_usage(
        self,
        db: Session,
        promo_code_id: str,
        order_id: str,
        discount_applied: int,
        user_id: Optional[str] = None,
        guest_email: Optional[str] = None
    ) -> PromoCodeUsage:
        """Record promo code usage for an order."""
        usage = PromoCodeUsage(
            promo_code_id=promo_code_id,
            order_id=order_id,
            user_id=user_id,
            guest_email=guest_email,
            discount_applied=discount_applied,
        )
        db.add(usage)

        # Also increment the usage counter
        self.increment_usage(db, promo_code_id)

        db.commit()
        db.refresh(usage)
        return usage


promo_code_crud = CRUDPromoCode()