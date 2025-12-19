# app/crud/crud_refund.py
from typing import List, Optional
from datetime import datetime, timezone
from sqlalchemy.orm import Session

from app.crud.base import CRUDBase
from app.models.refund import Refund
from app.schemas.payment import RefundCreate, RefundUpdate, RefundStatus


class CRUDRefund(CRUDBase[Refund, RefundCreate, RefundUpdate]):
    """CRUD operations for Refund model."""

    def get_by_provider_refund_id(
        self, db: Session, *, provider_refund_id: str
    ) -> Optional[Refund]:
        """Get a refund by the provider's refund ID."""
        return (
            db.query(self.model)
            .filter(self.model.provider_refund_id == provider_refund_id)
            .first()
        )

    def get_by_payment(
        self, db: Session, *, payment_id: str
    ) -> List[Refund]:
        """Get all refunds for a payment."""
        return (
            db.query(self.model)
            .filter(self.model.payment_id == payment_id)
            .order_by(self.model.created_at.desc())
            .all()
        )

    def get_by_order(
        self, db: Session, *, order_id: str
    ) -> List[Refund]:
        """Get all refunds for an order."""
        return (
            db.query(self.model)
            .filter(self.model.order_id == order_id)
            .order_by(self.model.created_at.desc())
            .all()
        )

    def get_by_idempotency_key(
        self, db: Session, *, idempotency_key: str
    ) -> Optional[Refund]:
        """Get a refund by its idempotency key."""
        return (
            db.query(self.model)
            .filter(self.model.idempotency_key == idempotency_key)
            .first()
        )

    def get_by_organization(
        self,
        db: Session,
        *,
        organization_id: str,
        status: Optional[RefundStatus] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> List[Refund]:
        """Get refunds for an organization with pagination."""
        query = db.query(self.model).filter(
            self.model.organization_id == organization_id
        )

        if status:
            query = query.filter(self.model.status == status.value)

        return (
            query.order_by(self.model.created_at.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

    def create_refund(
        self, db: Session, *, obj_in: RefundCreate
    ) -> Refund:
        """Create a new refund record."""
        db_obj = Refund(
            payment_id=obj_in.payment_id,
            order_id=obj_in.order_id,
            organization_id=obj_in.organization_id,
            initiated_by_user_id=obj_in.initiated_by_user_id,
            provider_code=obj_in.provider_code,
            status="pending",
            reason=obj_in.reason.value,
            reason_details=obj_in.reason_details,
            currency=obj_in.currency,
            amount=obj_in.amount,
            idempotency_key=obj_in.idempotency_key,
        )
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def update_status(
        self,
        db: Session,
        *,
        refund_id: str,
        status: RefundStatus,
        provider_refund_id: Optional[str] = None,
        failure_code: Optional[str] = None,
        failure_message: Optional[str] = None,
    ) -> Optional[Refund]:
        """Update refund status."""
        refund = self.get(db, id=refund_id)
        if not refund:
            return None

        refund.status = status.value
        refund.updated_at = datetime.now(timezone.utc)

        if status == RefundStatus.succeeded:
            refund.processed_at = datetime.now(timezone.utc)

        if provider_refund_id:
            refund.provider_refund_id = provider_refund_id
        if failure_code:
            refund.failure_code = failure_code
        if failure_message:
            refund.failure_message = failure_message

        db.add(refund)
        db.commit()
        db.refresh(refund)
        return refund

    def get_total_refunded_for_payment(
        self, db: Session, *, payment_id: str
    ) -> int:
        """Get the total refunded amount for a payment."""
        from sqlalchemy import func

        result = (
            db.query(func.sum(self.model.amount))
            .filter(
                self.model.payment_id == payment_id,
                self.model.status == RefundStatus.succeeded.value,
            )
            .scalar()
        )
        return result or 0

    def get_pending_refunds(
        self, db: Session, *, limit: int = 100
    ) -> List[Refund]:
        """Get all pending refunds."""
        return (
            db.query(self.model)
            .filter(self.model.status.in_(["pending", "processing"]))
            .limit(limit)
            .all()
        )


refund = CRUDRefund(Refund)
