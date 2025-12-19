# app/graphql/payment_queries.py
"""
GraphQL queries for payment-related operations.

These queries handle:
- Ticket types for events
- Order retrieval
- Payment details
- Refund information
"""
import strawberry
from typing import List, Optional
from strawberry.types import Info
from fastapi import HTTPException

from .. import crud
from .payment_types import (
    TicketTypeType,
    OrderType,
    OrderConnection,
    PaymentType,
    RefundType,
    OrderStatusEnum,
)


def get_event_ticket_types(
    event_id: str, info: Info
) -> List[TicketTypeType]:
    """
    Get ticket types for an event (public).
    Returns only active, on-sale ticket types.
    """
    db = info.context.db

    # Get the event to verify it's public or user has access
    event = crud.event.get(db, id=event_id)
    if not event:
        return []

    # Only return ticket types for public events or if user has access
    user = info.context.user
    can_access = False

    if event.is_public and not event.is_archived:
        can_access = True
    elif user:
        user_org_id = user.get("orgId")
        if user_org_id and event.organization_id == user_org_id:
            can_access = True

    if not can_access:
        return []

    return crud.ticket_type.get_available_ticket_types(db, event_id=event_id)


def get_order(order_id: str, info: Info) -> Optional[OrderType]:
    """
    Get order by ID (authenticated - owner or admin only).
    """
    db = info.context.db
    user = info.context.user

    if not user:
        return None

    order = crud.order.get_with_items(db, order_id=order_id)
    if not order:
        return None

    # Check authorization
    user_id = user.get("sub")
    user_org_id = user.get("orgId")

    # User can view their own orders, or organizers can view their org's orders
    if order.user_id == user_id:
        return order
    if user_org_id and order.organization_id == user_org_id:
        return order

    return None


def get_order_by_number(order_number: str, info: Info) -> Optional[OrderType]:
    """
    Get order by order number (for confirmation pages).
    """
    db = info.context.db
    user = info.context.user

    order = crud.order.get_by_order_number(db, order_number=order_number)
    if not order:
        return None

    # For guest orders, allow access without auth (they have the order number)
    if order.user_id is None:
        return order

    # For authenticated orders, verify ownership
    if user:
        user_id = user.get("sub")
        user_org_id = user.get("orgId")

        if order.user_id == user_id:
            return order
        if user_org_id and order.organization_id == user_org_id:
            return order

    return None


def get_my_orders(
    info: Info,
    status: Optional[OrderStatusEnum] = None,
    first: int = 20,
    after: Optional[str] = None,
) -> OrderConnection:
    """
    List orders for current user.
    """
    db = info.context.db
    user = info.context.user

    if not user:
        return OrderConnection(orders=[], totalCount=0, hasNextPage=False)

    user_id = user.get("sub")
    if not user_id:
        return OrderConnection(orders=[], totalCount=0, hasNextPage=False)

    # Parse cursor for pagination
    skip = 0
    if after:
        try:
            skip = int(after)
        except ValueError:
            skip = 0

    # Convert status if provided
    status_value = None
    if status:
        from app.schemas.payment import OrderStatus
        status_value = OrderStatus(status.value)

    orders, total = crud.order.get_by_user(
        db,
        user_id=user_id,
        status=status_value,
        skip=skip,
        limit=first + 1,  # Get one extra to check hasNextPage
    )

    has_next_page = len(orders) > first
    if has_next_page:
        orders = orders[:first]

    return OrderConnection(
        orders=orders,
        totalCount=total,
        hasNextPage=has_next_page,
    )


def get_event_orders(
    event_id: str,
    info: Info,
    status: Optional[OrderStatusEnum] = None,
    search: Optional[str] = None,
    first: int = 50,
    after: Optional[str] = None,
) -> OrderConnection:
    """
    List orders for an event (organizer only).
    """
    db = info.context.db
    user = info.context.user

    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")

    # Verify organizer access
    user_org_id = user.get("orgId")
    event = crud.event.get(db, id=event_id)

    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    if not user_org_id or event.organization_id != user_org_id:
        raise HTTPException(status_code=403, detail="Not authorized")

    # Parse cursor
    skip = 0
    if after:
        try:
            skip = int(after)
        except ValueError:
            skip = 0

    # Convert status if provided
    status_value = None
    if status:
        from app.schemas.payment import OrderStatus
        status_value = OrderStatus(status.value)

    orders, total = crud.order.get_by_event(
        db,
        event_id=event_id,
        status=status_value,
        search=search,
        skip=skip,
        limit=first + 1,
    )

    has_next_page = len(orders) > first
    if has_next_page:
        orders = orders[:first]

    return OrderConnection(
        orders=orders,
        totalCount=total,
        hasNextPage=has_next_page,
    )


def get_payment(payment_id: str, info: Info) -> Optional[PaymentType]:
    """
    Get payment details (authenticated - owner or admin only).
    """
    db = info.context.db
    user = info.context.user

    if not user:
        return None

    payment = crud.payment.get(db, id=payment_id)
    if not payment:
        return None

    # Get the order to check authorization
    order = crud.order.get(db, id=payment.order_id)
    if not order:
        return None

    user_id = user.get("sub")
    user_org_id = user.get("orgId")

    if order.user_id == user_id:
        return payment
    if user_org_id and order.organization_id == user_org_id:
        return payment

    return None


def get_order_refunds(order_id: str, info: Info) -> List[RefundType]:
    """
    Get refunds for an order (organizer only).
    """
    db = info.context.db
    user = info.context.user

    if not user:
        return []

    # Verify organizer access
    user_org_id = user.get("orgId")
    order = crud.order.get(db, id=order_id)

    if not order:
        return []

    if not user_org_id or order.organization_id != user_org_id:
        return []

    return crud.refund.get_by_order(db, order_id=order_id)


def get_ticket_types_by_event(event_id: str, info: Info) -> List[TicketTypeType]:
    """
    Get all ticket types for an event (organizer only - includes inactive).
    """
    db = info.context.db
    user = info.context.user

    if not user:
        return []

    # Verify organizer access
    user_org_id = user.get("orgId")
    event = crud.event.get(db, id=event_id)

    if not event:
        return []

    if not user_org_id or event.organization_id != user_org_id:
        return []

    return crud.ticket_type.get_by_event(
        db, event_id=event_id, include_inactive=True, include_archived=False
    )
