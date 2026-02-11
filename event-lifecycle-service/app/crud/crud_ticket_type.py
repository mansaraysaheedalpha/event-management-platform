# app/crud/crud_ticket_type.py
from typing import List, Optional
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from sqlalchemy import and_

from app.crud.base import CRUDBase
from app.models.ticket_type import TicketType
from app.schemas.payment import TicketTypeCreate, TicketTypeUpdate


class CRUDTicketType(CRUDBase[TicketType, TicketTypeCreate, TicketTypeUpdate]):
    """CRUD operations for TicketType model."""

    def get_by_event(
        self,
        db: Session,
        *,
        event_id: str,
        include_inactive: bool = False,
        include_archived: bool = False,
    ) -> List[TicketType]:
        """Get all ticket types for an event."""
        query = db.query(self.model).filter(self.model.event_id == event_id)

        if not include_inactive:
            query = query.filter(self.model.is_active == True)

        if not include_archived:
            query = query.filter(self.model.is_archived == False)

        return query.order_by(self.model.sort_order, self.model.created_at).all()

    def get_available_ticket_types(
        self, db: Session, *, event_id: str
    ) -> List[TicketType]:
        """
        Get ticket types that should be shown to attendees.

        Priority:
        1) Active, non-archived, non-hidden tickets in their sales window (on sale now)
        2) If none are currently on sale, fall back to the next eligible active tickets
           (ignoring sales window) so pricing is still exposed instead of defaulting to "free".
        """
        now = datetime.now(timezone.utc)

        base_filters = [
            self.model.event_id == event_id,
            self.model.is_active == True,  # noqa: E712
            self.model.is_archived == False,  # noqa: E712
            self.model.is_hidden == False,  # don't expose hidden ticket types
        ]

        # Pass 1: tickets currently on sale
        query_on_sale = (
            db.query(self.model)
            .filter(
                and_(
                    *base_filters,
                    (self.model.sales_start_at == None)
                    | (self.model.sales_start_at <= now),
                    (self.model.sales_end_at == None)
                    | (self.model.sales_end_at >= now),
                )
            )
            .order_by(self.model.sort_order, self.model.created_at)
        )
        tickets = query_on_sale.all()
        if tickets:
            return tickets

        # Pass 2: fallback to active, non-archived, non-hidden tickets even if outside window
        query_fallback = (
            db.query(self.model)
            .filter(and_(*base_filters))
            .order_by(self.model.sort_order, self.model.created_at)
        )
        return query_fallback.all()

    def create_for_event(
        self, db: Session, *, obj_in: TicketTypeCreate, organization_id: str
    ) -> TicketType:
        """Create a new ticket type for an event."""
        db_obj = TicketType(
            event_id=obj_in.event_id,
            organization_id=organization_id,
            name=obj_in.name,
            description=obj_in.description,
            price=obj_in.price,
            currency=obj_in.currency,
            quantity_total=obj_in.quantity_total,
            min_per_order=obj_in.min_per_order,
            max_per_order=obj_in.max_per_order,
            sales_start_at=obj_in.sales_start_at,
            sales_end_at=obj_in.sales_end_at,
            is_active=obj_in.is_active,
            is_hidden=obj_in.is_hidden,
            sort_order=obj_in.sort_order,
        )
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def increment_quantity_sold(
        self, db: Session, *, ticket_type_id: str, quantity: int
    ) -> Optional[TicketType]:
        """Increment the quantity sold and release corresponding reservation."""
        ticket_type = self.get(db, id=ticket_type_id)
        if not ticket_type:
            return None

        # Check if there's enough quantity
        if ticket_type.quantity_total is not None:
            if ticket_type.quantity_sold + quantity > ticket_type.quantity_total:
                return None

        ticket_type.quantity_sold += quantity
        # Release the reservation that was held for this purchase
        ticket_type.quantity_reserved = max(0, ticket_type.quantity_reserved - quantity)
        ticket_type.updated_at = datetime.now(timezone.utc)
        db.add(ticket_type)
        db.commit()
        db.refresh(ticket_type)
        return ticket_type

    def decrement_quantity_sold(
        self, db: Session, *, ticket_type_id: str, quantity: int
    ) -> Optional[TicketType]:
        """Decrement the quantity sold for a ticket type (for refunds)."""
        ticket_type = self.get(db, id=ticket_type_id)
        if not ticket_type:
            return None

        ticket_type.quantity_sold = max(0, ticket_type.quantity_sold - quantity)
        ticket_type.updated_at = datetime.now(timezone.utc)
        db.add(ticket_type)
        db.commit()
        db.refresh(ticket_type)
        return ticket_type

    def reserve_quantity(
        self, db: Session, *, ticket_type_id: str, quantity: int
    ) -> bool:
        """Reserve inventory for a pending order. Returns False if insufficient stock."""
        ticket_type = self.get(db, id=ticket_type_id)
        if not ticket_type:
            return False

        if ticket_type.quantity_total is not None:
            available = ticket_type.quantity_total - ticket_type.quantity_sold - ticket_type.quantity_reserved
            if available < quantity:
                return False

        ticket_type.quantity_reserved += quantity
        ticket_type.updated_at = datetime.now(timezone.utc)
        db.add(ticket_type)
        db.commit()
        return True

    def release_quantity(
        self, db: Session, *, ticket_type_id: str, quantity: int
    ) -> bool:
        """Release reserved inventory (order cancelled/expired)."""
        ticket_type = self.get(db, id=ticket_type_id)
        if not ticket_type:
            return False

        ticket_type.quantity_reserved = max(0, ticket_type.quantity_reserved - quantity)
        ticket_type.updated_at = datetime.now(timezone.utc)
        db.add(ticket_type)
        db.commit()
        return True

    def is_available(
        self, db: Session, *, ticket_type_id: str, quantity: int = 1
    ) -> bool:
        """Check if a ticket type is available for purchase."""
        ticket_type = self.get(db, id=ticket_type_id)
        if not ticket_type:
            return False

        if not ticket_type.is_active or ticket_type.is_archived:
            return False

        now = datetime.now(timezone.utc)

        # Check sales window
        if ticket_type.sales_start_at and now < ticket_type.sales_start_at:
            return False
        if ticket_type.sales_end_at and now > ticket_type.sales_end_at:
            return False

        # Check quantity (include reserved tickets from pending orders)
        if ticket_type.quantity_total is not None:
            available = ticket_type.quantity_total - ticket_type.quantity_sold - ticket_type.quantity_reserved
            if available < quantity:
                return False

        return True


ticket_type = CRUDTicketType(TicketType)
