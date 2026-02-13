from sqlalchemy.orm import Session
from sqlalchemy import and_
from typing import List, Optional
from datetime import datetime, timezone

from app.models.offer_purchase import OfferPurchase
from app.models.offer import Offer


class CRUDOfferPurchase:
    def __init__(self):
        self.model = OfferPurchase

    def get(self, db: Session, id: str) -> Optional[OfferPurchase]:
        """Get a single offer purchase by ID."""
        return db.query(self.model).filter(self.model.id == id).first()

    def get_by_order_id(self, db: Session, *, order_id: str) -> Optional[OfferPurchase]:
        """Get a purchase by Stripe checkout session ID (order_id).
        Used for webhook idempotency — prevents duplicate processing."""
        return db.query(self.model).filter(self.model.order_id == order_id).first()

    def create(
        self,
        db: Session,
        *,
        offer_id: str,
        user_id: str,
        quantity: int,
        unit_price: float,
        currency: str = "USD",
        order_id: Optional[str] = None,
        fulfillment_type: Optional[str] = None,
        auto_commit: bool = True
    ) -> OfferPurchase:
        """
        Create a new offer purchase record.

        This should be called after payment is confirmed.
        Set auto_commit=False when calling within a larger transaction.
        """
        total_price = unit_price * quantity

        purchase = OfferPurchase(
            offer_id=offer_id,
            user_id=user_id,
            order_id=order_id,
            quantity=quantity,
            unit_price=unit_price,
            total_price=total_price,
            currency=currency,
            fulfillment_type=fulfillment_type,
            fulfillment_status="PENDING"
        )

        db.add(purchase)
        if auto_commit:
            db.commit()
            db.refresh(purchase)
        else:
            db.flush()
        return purchase

    def get_user_purchases(
        self,
        db: Session,
        *,
        user_id: str,
        event_id: Optional[str] = None
    ) -> List[OfferPurchase]:
        """
        Get all purchases by a user, optionally filtered by event.
        """
        query = db.query(self.model).filter(self.model.user_id == user_id)

        if event_id:
            # Join with offers to filter by event
            query = query.join(Offer).filter(Offer.event_id == event_id)

        return query.order_by(self.model.purchased_at.desc()).all()

    def get_offer_purchases(
        self,
        db: Session,
        *,
        offer_id: str
    ) -> List[OfferPurchase]:
        """Get all purchases for a specific offer."""
        return db.query(self.model).filter(
            self.model.offer_id == offer_id
        ).order_by(self.model.purchased_at.desc()).all()

    def update_fulfillment_status(
        self,
        db: Session,
        *,
        purchase_id: str,
        status: str,
        digital_content_url: Optional[str] = None,
        access_code: Optional[str] = None,
        tracking_number: Optional[str] = None
    ) -> Optional[OfferPurchase]:
        """
        Update fulfillment status of a purchase.

        Valid statuses: PENDING, PROCESSING, FULFILLED, FAILED, REFUNDED
        """
        purchase = self.get(db, id=purchase_id)

        if not purchase:
            return None

        purchase.fulfillment_status = status

        if digital_content_url:
            purchase.digital_content_url = digital_content_url

        if access_code:
            purchase.access_code = access_code

        if tracking_number:
            purchase.tracking_number = tracking_number

        if status == "FULFILLED":
            purchase.fulfilled_at = datetime.now(timezone.utc)
        elif status == "REFUNDED":
            purchase.refunded_at = datetime.now(timezone.utc)

        db.commit()
        db.refresh(purchase)
        return purchase

    def get_pending_fulfillments(
        self,
        db: Session,
        limit: int = 100
    ) -> List[OfferPurchase]:
        """
        Get pending fulfillments for processing.
        Used by background jobs.
        """
        return db.query(self.model).filter(
            self.model.fulfillment_status == "PENDING"
        ).limit(limit).all()

    def get_user_purchase_for_offer(
        self,
        db: Session,
        *,
        user_id: str,
        offer_id: str
    ) -> Optional[OfferPurchase]:
        """
        Check if user has already purchased a specific offer.
        Returns most recent purchase if exists.
        """
        return db.query(self.model).filter(
            and_(
                self.model.user_id == user_id,
                self.model.offer_id == offer_id,
                self.model.fulfillment_status != "REFUNDED"
            )
        ).order_by(self.model.purchased_at.desc()).first()

    def get_revenue_by_offer(
        self,
        db: Session,
        *,
        offer_id: str
    ) -> float:
        """Calculate total revenue for an offer."""
        from sqlalchemy import func

        result = db.query(
            func.sum(self.model.total_price)
        ).filter(
            and_(
                self.model.offer_id == offer_id,
                self.model.fulfillment_status != "REFUNDED"
            )
        ).scalar()

        return float(result) if result else 0.0

    def get_revenue_by_event(
        self,
        db: Session,
        *,
        event_id: str
    ) -> float:
        """Calculate total revenue for all offers in an event."""
        from sqlalchemy import func

        result = db.query(
            func.sum(self.model.total_price)
        ).join(Offer).filter(
            and_(
                Offer.event_id == event_id,
                self.model.fulfillment_status != "REFUNDED"
            )
        ).scalar()

        return float(result) if result else 0.0


# Create singleton instance
offer_purchase = CRUDOfferPurchase()
