from sqlalchemy.orm import Session
from sqlalchemy import and_, or_
from typing import List, Optional
from datetime import datetime, timezone
from .base import CRUDBase
from app.models.offer import Offer
from app.schemas.offer import OfferCreate, OfferUpdate


class CRUDOffer(CRUDBase[Offer, OfferCreate, OfferUpdate]):
    def get_multi_by_event(
        self,
        db: Session,
        *,
        event_id: str,
        active_only: bool = False,
        placement: Optional[str] = None
    ) -> List[Offer]:
        """Get all offers for an event with optional filtering."""
        query = db.query(self.model).filter(
            self.model.event_id == event_id,
            self.model.is_archived == False
        )

        if active_only:
            query = query.filter(self.model.is_active == True)

        if placement:
            query = query.filter(self.model.placement == placement)

        return query.order_by(self.model.created_at.desc()).all()

    def get_active_offers(
        self,
        db: Session,
        *,
        event_id: str,
        placement: Optional[str] = None,
        session_id: Optional[str] = None
    ) -> List[Offer]:
        """
        Get currently active and available offers for an event.

        Filters by:
        - is_active = true
        - is_archived = false
        - NOW() between starts_at and expires_at
        - placement (if specified)
        - targeting rules (if session_id specified)
        - inventory available > 0
        """
        now = datetime.now(timezone.utc)

        query = db.query(self.model).filter(
            self.model.event_id == event_id,
            self.model.is_active == True,
            self.model.is_archived == False,
            or_(
                self.model.starts_at == None,
                self.model.starts_at <= now
            ),
            or_(
                self.model.expires_at == None,
                self.model.expires_at > now
            )
        )

        if placement:
            query = query.filter(self.model.placement == placement)

        # Get offers and filter by availability
        offers = query.all()

        # Filter by session targeting if session_id provided
        if session_id:
            offers = [
                offer for offer in offers
                if not offer.target_sessions or session_id in offer.target_sessions
            ]

        # Filter by inventory availability
        offers = [
            offer for offer in offers
            if offer.inventory_available > 0
        ]

        return offers

    def check_availability(
        self,
        db: Session,
        *,
        offer_id: str,
        quantity: int = 1
    ) -> tuple[bool, Optional[str]]:
        """
        Check if an offer is available for purchase.

        Returns: (is_available, reason_if_not)
        """
        offer = self.get(db, id=offer_id)

        if not offer:
            return False, "Offer not found"

        if offer.is_archived:
            return False, "Offer is no longer available"

        if not offer.is_active:
            return False, "Offer is not active"

        now = datetime.now(timezone.utc)

        if offer.starts_at and now < offer.starts_at:
            return False, "Offer has not started yet"

        if offer.expires_at and now > offer.expires_at:
            return False, "Offer has expired"

        if offer.inventory_available < quantity:
            return False, f"Only {offer.inventory_available} items available"

        return True, None

    def reserve_inventory(
        self,
        db: Session,
        *,
        offer_id: str,
        quantity: int
    ) -> Optional[Offer]:
        """
        Reserve inventory for an offer (used during checkout).
        Increments inventory_reserved.
        Uses row-level locking to prevent race conditions.
        """
        # Use SELECT FOR UPDATE to lock the row
        offer = db.query(self.model).filter(
            self.model.id == offer_id
        ).with_for_update().first()

        if not offer:
            return None

        # Check if we have enough inventory
        if offer.inventory_available < quantity:
            return None

        offer.inventory_reserved += quantity
        db.commit()
        db.refresh(offer)
        return offer

    def release_inventory(
        self,
        db: Session,
        *,
        offer_id: str,
        quantity: int
    ) -> Optional[Offer]:
        """
        Release reserved inventory (when checkout is cancelled/expired).
        Decrements inventory_reserved.
        Uses row-level locking to prevent race conditions.
        """
        # Use SELECT FOR UPDATE to lock the row
        offer = db.query(self.model).filter(
            self.model.id == offer_id
        ).with_for_update().first()

        if not offer:
            return None

        offer.inventory_reserved = max(0, offer.inventory_reserved - quantity)
        db.commit()
        db.refresh(offer)
        return offer

    def confirm_purchase(
        self,
        db: Session,
        *,
        offer_id: str,
        quantity: int
    ) -> Optional[Offer]:
        """
        Confirm a purchase - moves inventory from reserved to sold.
        Decrements inventory_reserved and increments inventory_sold.
        Uses row-level locking to prevent race conditions.
        """
        # Use SELECT FOR UPDATE to lock the row
        offer = db.query(self.model).filter(
            self.model.id == offer_id
        ).with_for_update().first()

        if not offer:
            return None

        # Move from reserved to sold
        to_move = min(offer.inventory_reserved, quantity)
        offer.inventory_reserved -= to_move
        offer.inventory_sold += to_move

        db.commit()
        db.refresh(offer)
        return offer

    def get_by_stripe_price(
        self,
        db: Session,
        *,
        stripe_price_id: str
    ) -> Optional[Offer]:
        """Get offer by Stripe price ID."""
        return db.query(self.model).filter(
            self.model.stripe_price_id == stripe_price_id
        ).first()

    def auto_expire_offers(self, db: Session) -> int:
        """
        Background task: Set is_active = false for expired offers.
        Returns count of expired offers.
        """
        now = datetime.now(timezone.utc)

        result = db.query(self.model).filter(
            self.model.is_active == True,
            self.model.expires_at != None,
            self.model.expires_at < now
        ).update({"is_active": False})

        db.commit()
        return result


# Create singleton instance
offer = CRUDOffer(Offer)
