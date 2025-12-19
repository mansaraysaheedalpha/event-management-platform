# app/crud/crud_payment.py
from typing import List, Optional
from datetime import datetime, timezone
from sqlalchemy.orm import Session, joinedload

from app.crud.base import CRUDBase
from app.models.payment import Payment
from app.schemas.payment import PaymentCreate, PaymentUpdate, PaymentStatus


class CRUDPayment(CRUDBase[Payment, PaymentCreate, PaymentUpdate]):
    """CRUD operations for Payment model."""

    def get_with_refunds(self, db: Session, *, payment_id: str) -> Optional[Payment]:
        """Get a payment with its refunds loaded."""
        return (
            db.query(self.model)
            .options(joinedload(self.model.refunds))
            .filter(self.model.id == payment_id)
            .first()
        )

    def get_by_provider_payment_id(
        self, db: Session, *, provider_payment_id: str
    ) -> Optional[Payment]:
        """Get a payment by the provider's payment ID."""
        return (
            db.query(self.model)
            .filter(self.model.provider_payment_id == provider_payment_id)
            .first()
        )

    def get_by_provider_intent_id(
        self, db: Session, *, provider_intent_id: str
    ) -> Optional[Payment]:
        """Get a payment by the provider's intent ID."""
        return (
            db.query(self.model)
            .filter(self.model.provider_intent_id == provider_intent_id)
            .first()
        )

    def get_by_order(
        self, db: Session, *, order_id: str
    ) -> List[Payment]:
        """Get all payments for an order."""
        return (
            db.query(self.model)
            .filter(self.model.order_id == order_id)
            .order_by(self.model.created_at.desc())
            .all()
        )

    def get_successful_payment(
        self, db: Session, *, order_id: str
    ) -> Optional[Payment]:
        """Get the successful payment for an order."""
        return (
            db.query(self.model)
            .filter(
                self.model.order_id == order_id,
                self.model.status == PaymentStatus.succeeded.value,
            )
            .first()
        )

    def get_by_idempotency_key(
        self, db: Session, *, idempotency_key: str
    ) -> Optional[Payment]:
        """Get a payment by its idempotency key."""
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
        status: Optional[PaymentStatus] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> List[Payment]:
        """Get payments for an organization with pagination."""
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

    def create_payment(
        self, db: Session, *, obj_in: PaymentCreate
    ) -> Payment:
        """Create a new payment record."""
        db_obj = Payment(
            order_id=obj_in.order_id,
            organization_id=obj_in.organization_id,
            provider_code=obj_in.provider_code,
            provider_payment_id=obj_in.provider_payment_id,
            provider_intent_id=obj_in.provider_intent_id,
            status=obj_in.status.value,
            currency=obj_in.currency,
            amount=obj_in.amount,
            net_amount=obj_in.net_amount,
            payment_method_type=obj_in.payment_method_type,
            payment_method_details=obj_in.payment_method_details,
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
        payment_id: str,
        status: PaymentStatus,
        provider_fee: Optional[int] = None,
        payment_method_type: Optional[str] = None,
        payment_method_details: Optional[dict] = None,
        failure_code: Optional[str] = None,
        failure_message: Optional[str] = None,
        risk_score: Optional[int] = None,
        risk_level: Optional[str] = None,
        provider_metadata: Optional[dict] = None,
    ) -> Optional[Payment]:
        """Update payment status and details."""
        payment = self.get(db, id=payment_id)
        if not payment:
            return None

        payment.status = status.value
        payment.updated_at = datetime.now(timezone.utc)

        if status == PaymentStatus.succeeded:
            payment.processed_at = datetime.now(timezone.utc)

        if provider_fee is not None:
            payment.provider_fee = provider_fee
            payment.net_amount = payment.amount - provider_fee

        if payment_method_type:
            payment.payment_method_type = payment_method_type
        if payment_method_details:
            payment.payment_method_details = payment_method_details
        if failure_code:
            payment.failure_code = failure_code
        if failure_message:
            payment.failure_message = failure_message
        if risk_score is not None:
            payment.risk_score = risk_score
        if risk_level:
            payment.risk_level = risk_level
        if provider_metadata:
            payment.provider_metadata = provider_metadata

        db.add(payment)
        db.commit()
        db.refresh(payment)
        return payment

    def add_refunded_amount(
        self, db: Session, *, payment_id: str, amount: int
    ) -> Optional[Payment]:
        """Add to the refunded amount for a payment."""
        payment = self.get(db, id=payment_id)
        if not payment:
            return None

        payment.amount_refunded += amount
        payment.updated_at = datetime.now(timezone.utc)

        # Update status if fully refunded
        if payment.amount_refunded >= payment.amount:
            payment.status = PaymentStatus.refunded.value
        else:
            payment.status = PaymentStatus.partially_refunded.value

        db.add(payment)
        db.commit()
        db.refresh(payment)
        return payment

    def get_payment_stats_by_organization(
        self, db: Session, *, organization_id: str
    ) -> dict:
        """Get payment statistics for an organization."""
        from sqlalchemy import func

        stats = (
            db.query(
                func.count(self.model.id).label("total_payments"),
                func.sum(
                    func.case(
                        (self.model.status == "succeeded", 1),
                        else_=0,
                    )
                ).label("successful_payments"),
                func.sum(
                    func.case(
                        (self.model.status == "succeeded", self.model.amount),
                        else_=0,
                    )
                ).label("total_amount"),
                func.sum(
                    func.case(
                        (self.model.status == "succeeded", self.model.provider_fee),
                        else_=0,
                    )
                ).label("total_fees"),
                func.sum(self.model.amount_refunded).label("total_refunded"),
            )
            .filter(self.model.organization_id == organization_id)
            .first()
        )

        return {
            "total_payments": stats.total_payments or 0,
            "successful_payments": stats.successful_payments or 0,
            "total_amount": stats.total_amount or 0,
            "total_fees": stats.total_fees or 0,
            "total_refunded": stats.total_refunded or 0,
        }


payment = CRUDPayment(Payment)
