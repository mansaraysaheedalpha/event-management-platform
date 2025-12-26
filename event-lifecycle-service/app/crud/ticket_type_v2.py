# app/crud/ticket_type.py
from sqlalchemy.orm import Session
from sqlalchemy import and_, update as sql_update
from typing import List, Optional
from datetime import datetime, timezone

from app.models.ticket_type import TicketType
from app.schemas.ticket_management import TicketTypeCreate, TicketTypeUpdate


class CRUDTicketType:
    """CRUD operations for ticket types."""

    def get(self, db: Session, ticket_type_id: str) -> Optional[TicketType]:
        """Get a ticket type by ID."""
        return db.query(TicketType).filter(TicketType.id == ticket_type_id).first()

    def get_by_event(
        self,
        db: Session,
        event_id: str,
        include_inactive: bool = False,
        include_hidden: bool = False
    ) -> List[TicketType]:
        """Get all ticket types for an event."""
        query = db.query(TicketType).filter(TicketType.event_id == event_id)

        if not include_inactive:
            query = query.filter(TicketType.is_active == True)

        if not include_hidden:
            query = query.filter(TicketType.is_hidden == False)

        return query.order_by(TicketType.sort_order, TicketType.created_at).all()

    def get_available_for_purchase(
        self,
        db: Session,
        event_id: str
    ) -> List[TicketType]:
        """Get ticket types that are currently available for purchase."""
        now = datetime.now(timezone.utc)

        query = db.query(TicketType).filter(
            and_(
                TicketType.event_id == event_id,
                TicketType.is_active == True,
                TicketType.is_hidden == False,
            )
        ).order_by(TicketType.sort_order)

        ticket_types = query.all()

        # Filter by sales window and availability in Python
        available = []
        for tt in ticket_types:
            if tt.is_on_sale:
                available.append(tt)

        return available

    def create(
        self,
        db: Session,
        obj_in: TicketTypeCreate,
        organization_id: str,
        created_by: Optional[str] = None
    ) -> TicketType:
        """Create a new ticket type."""
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
            is_hidden=obj_in.is_hidden,
            sort_order=obj_in.sort_order,
            created_by=created_by,
        )
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def update(
        self,
        db: Session,
        ticket_type_id: str,
        obj_in: TicketTypeUpdate
    ) -> Optional[TicketType]:
        """Update a ticket type."""
        db_obj = self.get(db, ticket_type_id)
        if not db_obj:
            return None

        update_data = obj_in.model_dump(exclude_unset=True)
        update_data['updated_at'] = datetime.now(timezone.utc)

        for field, value in update_data.items():
            setattr(db_obj, field, value)

        db.commit()
        db.refresh(db_obj)
        return db_obj

    def delete(self, db: Session, ticket_type_id: str) -> bool:
        """Delete a ticket type (only if no sales)."""
        db_obj = self.get(db, ticket_type_id)
        if not db_obj:
            return False

        if db_obj.quantity_sold > 0:
            raise ValueError("Cannot delete ticket type with existing sales")

        db.delete(db_obj)
        db.commit()
        return True

    def reorder(
        self,
        db: Session,
        event_id: str,
        ticket_type_ids: List[str]
    ) -> List[TicketType]:
        """Reorder ticket types for an event."""
        for index, tt_id in enumerate(ticket_type_ids):
            db.query(TicketType).filter(
                and_(TicketType.id == tt_id, TicketType.event_id == event_id)
            ).update({"sort_order": index})

        db.commit()
        return self.get_by_event(db, event_id, include_inactive=True)

    def duplicate(
        self,
        db: Session,
        ticket_type_id: str,
        created_by: Optional[str] = None
    ) -> Optional[TicketType]:
        """Duplicate a ticket type."""
        original = self.get(db, ticket_type_id)
        if not original:
            return None

        db_obj = TicketType(
            event_id=original.event_id,
            organization_id=original.organization_id,
            name=f"{original.name} (Copy)",
            description=original.description,
            price=original.price,
            currency=original.currency,
            quantity_total=original.quantity_total,
            min_per_order=original.min_per_order,
            max_per_order=original.max_per_order,
            sales_start_at=original.sales_start_at,
            sales_end_at=original.sales_end_at,
            is_hidden=True,  # Start as hidden
            is_active=False,  # Start as inactive
            sort_order=original.sort_order + 1,
            created_by=created_by,
        )
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def reserve_inventory(
        self,
        db: Session,
        ticket_type_id: str,
        quantity: int
    ) -> bool:
        """Reserve inventory for a pending order."""
        db_obj = self.get(db, ticket_type_id)
        if not db_obj:
            return False

        # Check availability
        if db_obj.quantity_total is not None:
            available = db_obj.quantity_total - db_obj.quantity_sold - db_obj.quantity_reserved
            if available < quantity:
                return False

        db_obj.quantity_reserved += quantity
        db.commit()
        return True

    def release_reservation(
        self,
        db: Session,
        ticket_type_id: str,
        quantity: int
    ) -> bool:
        """Release reserved inventory."""
        db_obj = self.get(db, ticket_type_id)
        if not db_obj:
            return False

        db_obj.quantity_reserved = max(0, db_obj.quantity_reserved - quantity)
        db.commit()
        return True

    def confirm_sale(
        self,
        db: Session,
        ticket_type_id: str,
        quantity: int
    ) -> bool:
        """Convert reservation to sale (after payment)."""
        db_obj = self.get(db, ticket_type_id)
        if not db_obj:
            return False

        db_obj.quantity_sold += quantity
        db_obj.quantity_reserved = max(0, db_obj.quantity_reserved - quantity)
        db.commit()
        return True


ticket_type_crud = CRUDTicketType()
