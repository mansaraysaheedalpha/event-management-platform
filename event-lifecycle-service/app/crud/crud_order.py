# app/crud/crud_order.py
from typing import List, Optional, Tuple
from datetime import datetime, timezone, timedelta
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_, or_

from app.crud.base import CRUDBase
from app.models.order import Order
from app.models.order_item import OrderItem
from app.schemas.payment import OrderCreate, OrderUpdate, OrderStatus


class CRUDOrder(CRUDBase[Order, OrderCreate, OrderUpdate]):
    """CRUD operations for Order model."""

    def get_with_items(self, db: Session, *, order_id: str) -> Optional[Order]:
        """Get an order with its items loaded."""
        return (
            db.query(self.model)
            .options(joinedload(self.model.items))
            .filter(self.model.id == order_id)
            .first()
        )

    def get_by_order_number(
        self, db: Session, *, order_number: str
    ) -> Optional[Order]:
        """Get an order by its human-readable order number."""
        return (
            db.query(self.model)
            .options(joinedload(self.model.items))
            .filter(self.model.order_number == order_number)
            .first()
        )

    def get_by_payment_intent(
        self, db: Session, *, payment_intent_id: str
    ) -> Optional[Order]:
        """Get an order by its payment intent ID."""
        return (
            db.query(self.model)
            .options(joinedload(self.model.items))
            .filter(self.model.payment_intent_id == payment_intent_id)
            .first()
        )

    def get_by_user(
        self,
        db: Session,
        *,
        user_id: str,
        status: Optional[OrderStatus] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> Tuple[List[Order], int]:
        """Get orders for a user with pagination."""
        query = db.query(self.model).filter(self.model.user_id == user_id)

        if status:
            query = query.filter(self.model.status == status.value)

        total = query.count()
        orders = (
            query.options(joinedload(self.model.items))
            .order_by(self.model.created_at.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

        return orders, total

    def get_by_event(
        self,
        db: Session,
        *,
        event_id: str,
        status: Optional[OrderStatus] = None,
        search: Optional[str] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> Tuple[List[Order], int]:
        """Get orders for an event with pagination and filtering."""
        query = db.query(self.model).filter(self.model.event_id == event_id)

        if status:
            query = query.filter(self.model.status == status.value)

        if search:
            search_pattern = f"%{search}%"
            query = query.filter(
                or_(
                    self.model.order_number.ilike(search_pattern),
                    self.model.guest_email.ilike(search_pattern),
                    self.model.guest_first_name.ilike(search_pattern),
                    self.model.guest_last_name.ilike(search_pattern),
                )
            )

        total = query.count()
        orders = (
            query.options(joinedload(self.model.items))
            .order_by(self.model.created_at.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

        return orders, total

    def get_by_organization(
        self,
        db: Session,
        *,
        organization_id: str,
        status: Optional[OrderStatus] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> Tuple[List[Order], int]:
        """Get orders for an organization with pagination."""
        query = db.query(self.model).filter(
            self.model.organization_id == organization_id
        )

        if status:
            query = query.filter(self.model.status == status.value)

        total = query.count()
        orders = (
            query.options(joinedload(self.model.items))
            .order_by(self.model.created_at.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

        return orders, total

    def create_order(
        self,
        db: Session,
        *,
        obj_in: OrderCreate,
        organization_id: str,
        order_number: str,
    ) -> Order:
        """Create a new order."""
        db_obj = Order(
            order_number=order_number,
            event_id=obj_in.event_id,
            organization_id=organization_id,
            user_id=obj_in.user_id,
            guest_email=obj_in.guest_email,
            guest_first_name=obj_in.guest_first_name,
            guest_last_name=obj_in.guest_last_name,
            guest_phone=obj_in.guest_phone,
            status="pending",
            currency=obj_in.currency,
            subtotal=obj_in.subtotal,
            discount_amount=obj_in.discount_amount,
            tax_amount=obj_in.tax_amount,
            platform_fee=obj_in.platform_fee,
            total_amount=obj_in.total_amount,
            promo_code_id=obj_in.promo_code_id,
            expires_at=obj_in.expires_at,
            ip_address=obj_in.ip_address,
            user_agent=obj_in.user_agent,
        )
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def add_item(
        self,
        db: Session,
        *,
        order_id: str,
        ticket_type_id: str,
        quantity: int,
        unit_price: int,
        ticket_type_name: str,
        ticket_type_description: Optional[str] = None,
    ) -> OrderItem:
        """Add an item to an order."""
        item = OrderItem(
            order_id=order_id,
            ticket_type_id=ticket_type_id,
            quantity=quantity,
            unit_price=unit_price,
            total_price=quantity * unit_price,
            ticket_type_name=ticket_type_name,
            ticket_type_description=ticket_type_description,
        )
        db.add(item)
        db.commit()
        db.refresh(item)
        return item

    def update_status(
        self,
        db: Session,
        *,
        order_id: str,
        status: OrderStatus,
        payment_provider: Optional[str] = None,
        payment_intent_id: Optional[str] = None,
    ) -> Optional[Order]:
        """Update order status."""
        order = self.get(db, id=order_id)
        if not order:
            return None

        order.status = status.value
        order.updated_at = datetime.now(timezone.utc)

        if payment_provider:
            order.payment_provider = payment_provider
        if payment_intent_id:
            order.payment_intent_id = payment_intent_id

        if status == OrderStatus.completed:
            order.completed_at = datetime.now(timezone.utc)
        elif status == OrderStatus.cancelled:
            order.cancelled_at = datetime.now(timezone.utc)

        db.add(order)
        db.commit()
        db.refresh(order)
        return order

    def mark_completed(
        self, db: Session, *, order_id: str
    ) -> Optional[Order]:
        """Mark an order as completed."""
        return self.update_status(db, order_id=order_id, status=OrderStatus.completed)

    def mark_cancelled(
        self, db: Session, *, order_id: str
    ) -> Optional[Order]:
        """Mark an order as cancelled."""
        return self.update_status(db, order_id=order_id, status=OrderStatus.cancelled)

    def mark_expired(
        self, db: Session, *, order_id: str
    ) -> Optional[Order]:
        """Mark an order as expired."""
        return self.update_status(db, order_id=order_id, status=OrderStatus.expired)

    def get_expired_pending_orders(
        self, db: Session, *, limit: int = 100
    ) -> List[Order]:
        """Get pending orders that have expired."""
        now = datetime.now(timezone.utc)
        return (
            db.query(self.model)
            .filter(
                and_(
                    self.model.status == "pending",
                    self.model.expires_at != None,
                    self.model.expires_at < now,
                )
            )
            .limit(limit)
            .all()
        )

    def get_order_stats_by_event(
        self, db: Session, *, event_id: str
    ) -> dict:
        """Get order statistics for an event."""
        from sqlalchemy import func

        stats = (
            db.query(
                func.count(self.model.id).label("total_orders"),
                func.sum(
                    func.case(
                        (self.model.status == "completed", 1),
                        else_=0,
                    )
                ).label("completed_orders"),
                func.sum(
                    func.case(
                        (self.model.status == "completed", self.model.total_amount),
                        else_=0,
                    )
                ).label("total_revenue"),
            )
            .filter(self.model.event_id == event_id)
            .first()
        )

        return {
            "total_orders": stats.total_orders or 0,
            "completed_orders": stats.completed_orders or 0,
            "total_revenue": stats.total_revenue or 0,
        }


order = CRUDOrder(Order)
