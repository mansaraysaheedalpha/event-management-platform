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
        """Get ticket types that are currently on sale and available."""
        now = datetime.now(timezone.utc)
        query = db.query(self.model).filter(
            and_(
                self.model.event_id == event_id,
                self.model.is_active == True,
                self.model.is_archived == False,
            )
        )

        # Filter by sales window
        query = query.filter(
            (self.model.sales_start_at == None) | (self.model.sales_start_at <= now)
        )
        query = query.filter(
            (self.model.sales_end_at == None) | (self.model.sales_end_at >= now)
        )

        return query.order_by(self.model.sort_order, self.model.created_at).all()

    def create_for_event(
        self, db: Session, *, obj_in: TicketTypeCreate
    ) -> TicketType:
        """Create a new ticket type for an event."""
        db_obj = TicketType(
            event_id=obj_in.event_id,
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
            sort_order=obj_in.sort_order,
        )
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def increment_quantity_sold(
        self, db: Session, *, ticket_type_id: str, quantity: int
    ) -> Optional[TicketType]:
        """Increment the quantity sold for a ticket type."""
        ticket_type = self.get(db, id=ticket_type_id)
        if not ticket_type:
            return None

        # Check if there's enough quantity
        if ticket_type.quantity_total is not None:
            if ticket_type.quantity_sold + quantity > ticket_type.quantity_total:
                return None

        ticket_type.quantity_sold += quantity
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

        # Check quantity
        if ticket_type.quantity_total is not None:
            available = ticket_type.quantity_total - ticket_type.quantity_sold
            if available < quantity:
                return False

        return True


ticket_type = CRUDTicketType(TicketType)
