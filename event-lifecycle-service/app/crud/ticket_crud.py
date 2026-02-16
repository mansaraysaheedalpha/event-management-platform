# app/crud/ticket_crud.py
import random
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_, func, or_
from typing import List, Optional, Tuple
from datetime import datetime, timezone, timedelta

from app.models.ticket import Ticket
from app.models.order_item import OrderItem
from app.schemas.ticket_management import TicketStatus


class CRUDTicket:
    """CRUD operations for tickets."""

    def get(self, db: Session, ticket_id: str) -> Optional[Ticket]:
        """Get a ticket by ID."""
        return db.query(Ticket).options(
            joinedload(Ticket.ticket_type),
            joinedload(Ticket.event),
            joinedload(Ticket.order)
        ).filter(Ticket.id == ticket_id).first()

    def get_by_code(
        self,
        db: Session,
        ticket_code: str,
        event_id: Optional[str] = None
    ) -> Optional[Ticket]:
        """Get a ticket by its code."""
        query = db.query(Ticket).options(
            joinedload(Ticket.ticket_type),
            joinedload(Ticket.event)
        ).filter(Ticket.ticket_code == ticket_code)

        if event_id:
            query = query.filter(Ticket.event_id == event_id)

        return query.first()

    def get_by_order(
        self,
        db: Session,
        order_id: str
    ) -> List[Ticket]:
        """Get all tickets for an order."""
        return db.query(Ticket).options(
            joinedload(Ticket.ticket_type)
        ).filter(
            Ticket.order_id == order_id
        ).order_by(Ticket.created_at).all()

    def get_by_event(
        self,
        db: Session,
        event_id: str,
        status: Optional[str] = None,
        search: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ) -> Tuple[List[Ticket], int]:
        """Get all tickets for an event with pagination."""
        query = db.query(Ticket).filter(Ticket.event_id == event_id)

        if status:
            query = query.filter(Ticket.status == status)

        if search:
            search_term = f"%{search}%"
            query = query.filter(
                or_(
                    Ticket.attendee_name.ilike(search_term),
                    Ticket.attendee_email.ilike(search_term),
                    Ticket.ticket_code.ilike(search_term)
                )
            )

        # Get total count
        total = query.count()

        # Get paginated results
        tickets = query.options(
            joinedload(Ticket.ticket_type)
        ).order_by(
            Ticket.created_at.desc()
        ).limit(limit).offset(offset).all()

        return tickets, total

    def get_by_user(
        self,
        db: Session,
        user_id: str,
        event_id: Optional[str] = None
    ) -> List[Ticket]:
        """Get all tickets for a user."""
        query = db.query(Ticket).options(
            joinedload(Ticket.ticket_type),
            joinedload(Ticket.event)
        ).filter(Ticket.user_id == user_id)

        if event_id:
            query = query.filter(Ticket.event_id == event_id)

        return query.order_by(Ticket.created_at.desc()).all()

    def get_by_email(
        self,
        db: Session,
        email: str,
        event_id: Optional[str] = None
    ) -> List[Ticket]:
        """Get all tickets for an email address."""
        query = db.query(Ticket).options(
            joinedload(Ticket.ticket_type),
            joinedload(Ticket.event)
        ).filter(func.lower(Ticket.attendee_email) == email.lower())

        if event_id:
            query = query.filter(Ticket.event_id == event_id)

        return query.order_by(Ticket.created_at.desc()).all()

    def generate_check_in_pin(self, db: Session, event_id: str) -> str:
        """Generate a 6-digit check-in PIN that is unique across all active events.

        Global uniqueness (not just per-event) is required because SMS check-in
        searches by PIN across all active events — if two concurrent events shared
        the same PIN, the wrong ticket could be checked in.

        Retries up to 10 times on collision, which is extremely rare given
        900,000 possible values.
        """
        from app.models.event import Event

        now = datetime.now(timezone.utc)
        for _ in range(10):
            pin = str(random.randint(100000, 999999))
            # Check across ALL active events (end_date >= now), not just this one
            existing = (
                db.query(Ticket.id)
                .join(Event, Ticket.event_id == Event.id)
                .filter(
                    and_(
                        Ticket.check_in_pin == pin,
                        Event.end_date >= now,
                    )
                )
                .first()
            )
            if not existing:
                return pin
        raise RuntimeError("Could not generate unique PIN after 10 attempts")

    def get_by_pin(
        self,
        db: Session,
        pin: str,
        event_id: str,
    ) -> Optional[Ticket]:
        """Look up a ticket by its check-in PIN within an event."""
        return db.query(Ticket).options(
            joinedload(Ticket.ticket_type),
            joinedload(Ticket.event),
        ).filter(
            and_(
                Ticket.event_id == event_id,
                Ticket.check_in_pin == pin,
            )
        ).first()

    def create(
        self,
        db: Session,
        order_id: str,
        order_item_id: str,
        ticket_type_id: str,
        event_id: str,
        attendee_name: str,
        attendee_email: str,
        user_id: Optional[str] = None
    ) -> Ticket:
        """Create a new ticket with an auto-generated SMS check-in PIN."""
        pin = self.generate_check_in_pin(db, event_id)
        db_obj = Ticket(
            order_id=order_id,
            order_item_id=order_item_id,
            ticket_type_id=ticket_type_id,
            event_id=event_id,
            user_id=user_id,
            attendee_email=attendee_email,
            attendee_name=attendee_name,
            status="valid",
            check_in_pin=pin,
        )
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def create_bulk(
        self,
        db: Session,
        tickets_data: List[dict]
    ) -> List[Ticket]:
        """Create multiple tickets at once, each with a unique PIN."""
        tickets = []
        for data in tickets_data:
            event_id = data.get("event_id")
            if event_id and "check_in_pin" not in data:
                data["check_in_pin"] = self.generate_check_in_pin(db, event_id)
            ticket = Ticket(**data)
            db.add(ticket)
            tickets.append(ticket)

        db.commit()

        for ticket in tickets:
            db.refresh(ticket)

        return tickets

    def check_in(
        self,
        db: Session,
        ticket_id: str,
        checked_in_by: str,
        location: Optional[str] = None
    ) -> Optional[Ticket]:
        """Check in a ticket using atomic UPDATE to prevent race conditions."""
        from sqlalchemy import update

        now = datetime.now(timezone.utc)
        result = db.execute(
            update(Ticket).where(
                and_(
                    Ticket.id == ticket_id,
                    Ticket.status == 'valid'
                )
            ).values(
                status='checked_in',
                checked_in_at=now,
                checked_in_by=checked_in_by,
                check_in_location=location,
                updated_at=now
            ).returning(Ticket.id)
        )
        db.commit()

        updated_id = result.scalar_one_or_none()
        if not updated_id:
            # Either ticket not found or already checked in
            ticket = self.get(db, ticket_id)
            if not ticket:
                return None
            raise ValueError(f"Ticket cannot be checked in. Current status: {ticket.status}")

        return self.get(db, updated_id)

    def reverse_check_in(
        self,
        db: Session,
        ticket_id: str
    ) -> Optional[Ticket]:
        """Reverse a check-in (undo) using atomic UPDATE to prevent race conditions."""
        from sqlalchemy import update

        now = datetime.now(timezone.utc)
        result = db.execute(
            update(Ticket).where(
                and_(
                    Ticket.id == ticket_id,
                    Ticket.status == 'checked_in'
                )
            ).values(
                status='valid',
                checked_in_at=None,
                checked_in_by=None,
                check_in_location=None,
                updated_at=now
            ).returning(Ticket.id)
        )
        db.commit()

        updated_id = result.scalar_one_or_none()
        if not updated_id:
            # Either ticket not found or not in checked_in status
            ticket = self.get(db, ticket_id)
            if not ticket:
                return None
            raise ValueError("Ticket is not checked in")

        return self.get(db, updated_id)

    def cancel(
        self,
        db: Session,
        ticket_id: str,
        reason: Optional[str] = None
    ) -> Optional[Ticket]:
        """Cancel a ticket."""
        ticket = self.get(db, ticket_id)
        if not ticket:
            return None

        if not ticket.can_cancel:
            raise ValueError(f"Ticket cannot be cancelled. Current status: {ticket.status}")

        ticket.status = "cancelled"
        ticket.updated_at = datetime.now(timezone.utc)

        db.commit()
        db.refresh(ticket)
        return ticket

    def transfer(
        self,
        db: Session,
        ticket_id: str,
        new_attendee_name: str,
        new_attendee_email: str,
        new_user_id: Optional[str] = None
    ) -> Optional[Ticket]:
        """Transfer a ticket to a new attendee."""
        ticket = self.get(db, ticket_id)
        if not ticket:
            return None

        if not ticket.can_transfer:
            raise ValueError(f"Ticket cannot be transferred. Current status: {ticket.status}")

        # Create a new ticket for the new owner
        new_ticket = Ticket(
            order_id=ticket.order_id,
            order_item_id=ticket.order_item_id,
            ticket_type_id=ticket.ticket_type_id,
            event_id=ticket.event_id,
            user_id=new_user_id,
            attendee_email=new_attendee_email,
            attendee_name=new_attendee_name,
            status="valid",
            transferred_from_ticket_id=ticket.id,
            transferred_at=datetime.now(timezone.utc)
        )
        db.add(new_ticket)

        # Mark original ticket as transferred
        ticket.status = "transferred"
        ticket.updated_at = datetime.now(timezone.utc)

        db.commit()
        db.refresh(new_ticket)
        return new_ticket

    def mark_refunded(
        self,
        db: Session,
        ticket_id: str
    ) -> Optional[Ticket]:
        """Mark a ticket as refunded."""
        ticket = self.get(db, ticket_id)
        if not ticket:
            return None

        ticket.status = "refunded"
        ticket.updated_at = datetime.now(timezone.utc)

        db.commit()
        db.refresh(ticket)
        return ticket

    def get_check_in_stats(
        self,
        db: Session,
        event_id: str
    ) -> dict:
        """Get check-in statistics for an event."""
        # Total tickets
        total = db.query(func.count(Ticket.id)).filter(
            and_(
                Ticket.event_id == event_id,
                Ticket.status.in_(["valid", "checked_in"])
            )
        ).scalar() or 0

        # Checked in
        checked_in = db.query(func.count(Ticket.id)).filter(
            and_(
                Ticket.event_id == event_id,
                Ticket.status == "checked_in"
            )
        ).scalar() or 0

        return {
            "total": total,
            "checked_in": checked_in,
            "remaining": total - checked_in,
            "percentage": round((checked_in / total * 100), 1) if total > 0 else 0
        }

    def get_sales_stats(
        self,
        db: Session,
        event_id: str
    ) -> dict:
        """Get sales statistics for an event.

        Returns ticket counts AND actual revenue (summed from
        OrderItem.unit_price) for each period — no more avg_price
        approximation.
        """
        now = datetime.now(timezone.utc)
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        week_start = today_start - timedelta(days=now.weekday())
        month_start = today_start.replace(day=1)

        active_filter = and_(
            Ticket.event_id == event_id,
            Ticket.status.notin_(["cancelled", "refunded"]),
        )

        # Total sold
        total = db.query(func.count(Ticket.id)).filter(
            active_filter
        ).scalar() or 0

        # Helper: count + revenue for a time period
        def _period_stats(since: datetime) -> Tuple[int, int]:
            row = (
                db.query(
                    func.count(Ticket.id),
                    func.coalesce(func.sum(OrderItem.unit_price), 0),
                )
                .join(OrderItem, Ticket.order_item_id == OrderItem.id)
                .filter(active_filter, Ticket.created_at >= since)
                .one()
            )
            return int(row[0]), int(row[1])

        sales_today, revenue_today = _period_stats(today_start)
        sales_this_week, revenue_this_week = _period_stats(week_start)
        sales_this_month, revenue_this_month = _period_stats(month_start)

        return {
            "total": total,
            "sales_today": sales_today,
            "sales_this_week": sales_this_week,
            "sales_this_month": sales_this_month,
            "revenue_today": revenue_today,
            "revenue_this_week": revenue_this_week,
            "revenue_this_month": revenue_this_month,
        }


ticket_crud = CRUDTicket()
