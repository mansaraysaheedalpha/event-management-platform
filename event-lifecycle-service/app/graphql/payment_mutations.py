# app/graphql/payment_mutations.py
"""
GraphQL mutations for payment-related operations.

These mutations handle:
- Checkout session creation
- Order cancellation
- Promo code application
- Refund initiation
- Ticket type management
- Promo code management
"""
import strawberry
import uuid
from typing import Optional
from strawberry.types import Info
from fastapi import HTTPException

from .. import crud
from ..schemas.payment import (
    CreateOrderInput as CreateOrderInputSchema,
    OrderItemCreate,
    TicketTypeCreate,
    TicketTypeUpdate,
    PromoCodeCreate,
    DiscountType,
    InitiateRefundInput as InitiateRefundInputSchema,
    RefundReason,
)
from ..services.payment.payment_service import PaymentService
from .payment_types import (
    CheckoutSessionType,
    OrderType,
    RefundType,
    TicketTypeType,
    PromoCodeType,
    PaymentIntentType,
    CreateOrderInput,
    InitiateRefundInput,
    TicketTypeCreateInput,
    TicketTypeUpdateInput,
    PromoCodeCreateInput,
)


async def create_checkout_session(
    input: CreateOrderInput, info: Info
) -> CheckoutSessionType:
    """
    Create a checkout session with order and payment intent.

    Returns checkout session with client secret for Stripe Elements.
    """
    db = info.context.db
    user = info.context.user
    request = info.context.request

    # Get user info from JWT token
    user_id = user.get("sub") if user else None
    user_email = user.get("email") if user else None
    user_first_name = user.get("firstName") or user.get("first_name") if user else None
    user_last_name = user.get("lastName") or user.get("last_name") if user else None

    # Determine checkout email/name - use authenticated user info or guest info
    if user_id and user_email:
        # Authenticated user - use their info from token
        checkout_email = user_email
        checkout_first_name = user_first_name or input.guestFirstName
        checkout_last_name = user_last_name or input.guestLastName
        checkout_phone = input.guestPhone  # Phone might not be in token
    elif input.guestEmail:
        # Guest checkout - use provided info
        checkout_email = input.guestEmail
        checkout_first_name = input.guestFirstName
        checkout_last_name = input.guestLastName
        checkout_phone = input.guestPhone
    else:
        raise HTTPException(
            status_code=400,
            detail="Email is required for guest checkout"
        )

    # Get the event to find organization
    event = crud.event.get(db, id=input.eventId)
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    # Build the input schema
    items = [
        OrderItemCreate(
            ticket_type_id=item.ticketTypeId,
            quantity=item.quantity,
        )
        for item in input.items
    ]

    order_input = CreateOrderInputSchema(
        event_id=input.eventId,
        items=items,
        promo_code=input.promoCode,
        guest_email=checkout_email,
        guest_first_name=checkout_first_name,
        guest_last_name=checkout_last_name,
        guest_phone=checkout_phone,
    )

    # Get request metadata
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    request_id = str(uuid.uuid4())

    # Create checkout session
    payment_service = PaymentService(db)
    try:
        session = await payment_service.create_checkout_session(
            input_data=order_input,
            organization_id=event.organization_id,
            user_id=user_id,
            ip_address=ip_address,
            user_agent=user_agent,
            request_id=request_id,
        )

        # Convert to GraphQL types
        payment_intent = None
        if session.payment_intent:
            payment_intent = PaymentIntentType(
                clientSecret=session.payment_intent.client_secret,
                intentId=session.payment_intent.intent_id,
                publishableKey=session.payment_intent.publishable_key,
                expiresAt=session.payment_intent.expires_at,
            )

        # Reload order with items
        order = crud.order.get_with_items(db, order_id=session.order.id)

        return CheckoutSessionType(
            order=order,
            paymentIntent=payment_intent,
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


async def cancel_order(order_id: str, info: Info) -> OrderType:
    """
    Cancel a pending order (before payment).
    """
    db = info.context.db
    user = info.context.user

    # Get order
    order = crud.order.get_with_items(db, order_id=order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    # Check authorization
    user_id = user.get("sub") if user else None
    user_org_id = user.get("orgId") if user else None

    # User can cancel their own orders, or organizers can cancel org orders
    is_authorized = False
    if user_id and order.user_id == user_id:
        is_authorized = True
    elif user_org_id and order.organization_id == user_org_id:
        is_authorized = True
    elif not order.user_id and order.guest_email:
        # Guest orders can be cancelled by anyone with order access
        is_authorized = True

    if not is_authorized:
        raise HTTPException(status_code=403, detail="Not authorized")

    # Cancel order
    payment_service = PaymentService(db)
    try:
        cancelled_order = await payment_service.cancel_order(
            order_id=order_id,
            user_id=user_id,
            request_id=str(uuid.uuid4()),
        )
        return cancelled_order
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


async def apply_promo_code(
    order_id: str, promo_code: str, info: Info
) -> OrderType:
    """
    Apply promo code to pending order.
    """
    db = info.context.db
    user = info.context.user

    # Get order
    order = crud.order.get_with_items(db, order_id=order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    if order.status != "pending":
        raise HTTPException(
            status_code=400,
            detail="Promo code can only be applied to pending orders"
        )

    # Check authorization
    user_id = user.get("sub") if user else None

    if order.user_id and order.user_id != user_id:
        raise HTTPException(status_code=403, detail="Not authorized")

    # Get and validate promo code
    promo = crud.promo_code.get_valid_promo_code(
        db,
        organization_id=order.organization_id,
        code=promo_code,
        event_id=order.event_id,
    )

    if not promo:
        raise HTTPException(status_code=400, detail="Invalid or expired promo code")

    # Calculate discount
    discount_amount = promo.calculate_discount(order.subtotal)

    # Update order
    order.promo_code_id = promo.id
    order.discount_amount = discount_amount
    order.total_amount = order.subtotal - discount_amount

    # Ensure minimum amount
    if order.total_amount < 50 and order.total_amount > 0:
        raise HTTPException(
            status_code=400,
            detail="Order total is below minimum amount after discount"
        )

    db.add(order)
    db.commit()
    db.refresh(order)

    return order


async def remove_promo_code(order_id: str, info: Info) -> OrderType:
    """
    Remove promo code from pending order.
    """
    db = info.context.db
    user = info.context.user

    # Get order
    order = crud.order.get_with_items(db, order_id=order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    if order.status != "pending":
        raise HTTPException(
            status_code=400,
            detail="Promo code can only be removed from pending orders"
        )

    # Check authorization
    user_id = user.get("sub") if user else None

    if order.user_id and order.user_id != user_id:
        raise HTTPException(status_code=403, detail="Not authorized")

    # Remove promo code
    order.promo_code_id = None
    order.discount_amount = 0
    order.total_amount = order.subtotal

    db.add(order)
    db.commit()
    db.refresh(order)

    return order


async def initiate_refund(input: InitiateRefundInput, info: Info) -> RefundType:
    """
    Initiate refund (organizer only).
    """
    db = info.context.db
    user = info.context.user

    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")

    # Get order
    order = crud.order.get_with_items(db, order_id=input.orderId)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    # Verify organizer access
    user_org_id = user.get("orgId")
    if not user_org_id or order.organization_id != user_org_id:
        raise HTTPException(status_code=403, detail="Not authorized")

    # Map reason
    reason = RefundReason(input.reason.value)

    # Create refund input
    refund_input = InitiateRefundInputSchema(
        order_id=input.orderId,
        amount=input.amount,
        reason=reason,
        reason_details=input.reasonDetails,
    )

    # Initiate refund
    payment_service = PaymentService(db)
    try:
        refund = await payment_service.initiate_refund(
            input_data=refund_input,
            initiated_by_user_id=user.get("sub"),
            request_id=str(uuid.uuid4()),
        )
        return refund
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


async def cancel_refund(refund_id: str, info: Info) -> RefundType:
    """
    Cancel pending refund (organizer only).
    """
    db = info.context.db
    user = info.context.user

    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")

    # Get refund
    refund = crud.refund.get(db, id=refund_id)
    if not refund:
        raise HTTPException(status_code=404, detail="Refund not found")

    # Verify organizer access
    user_org_id = user.get("orgId")
    if not user_org_id or refund.organization_id != user_org_id:
        raise HTTPException(status_code=403, detail="Not authorized")

    if refund.status not in ("pending", "processing"):
        raise HTTPException(
            status_code=400,
            detail=f"Cannot cancel refund with status: {refund.status}"
        )

    # Update refund status
    from ..schemas.payment import RefundStatus
    refund = crud.refund.update_status(
        db,
        refund_id=refund_id,
        status=RefundStatus.cancelled,
    )

    return refund


# ============================================
# Ticket Type Management (Organizer)
# ============================================

def create_ticket_type(input: TicketTypeCreateInput, info: Info) -> TicketTypeType:
    """
    Create a new ticket type for an event (organizer only).
    """
    db = info.context.db
    user = info.context.user

    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")

    # Verify event exists and user has access
    event = crud.event.get(db, id=input.eventId)
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    user_org_id = user.get("orgId")
    if not user_org_id or event.organization_id != user_org_id:
        raise HTTPException(status_code=403, detail="Not authorized")

    # Create ticket type
    ticket_type_create = TicketTypeCreate(
        event_id=input.eventId,
        name=input.name,
        description=input.description,
        price=input.price,
        currency=input.currency,
        quantity_total=input.quantityTotal,
        min_per_order=input.minPerOrder,
        max_per_order=input.maxPerOrder,
        sales_start_at=input.salesStartAt,
        sales_end_at=input.salesEndAt,
        is_active=input.isActive,
        is_hidden=input.isHidden,
        sort_order=input.sortOrder,
    )

    ticket_type = crud.ticket_type.create_for_event(
        db, obj_in=ticket_type_create, organization_id=user_org_id
    )
    return ticket_type


def update_ticket_type(
    ticket_type_id: str, input: TicketTypeUpdateInput, info: Info
) -> TicketTypeType:
    """
    Update a ticket type (organizer only).
    """
    db = info.context.db
    user = info.context.user

    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")

    # Get ticket type
    ticket_type = crud.ticket_type.get(db, id=ticket_type_id)
    if not ticket_type:
        raise HTTPException(status_code=404, detail="Ticket type not found")

    # Verify user has access
    event = crud.event.get(db, id=ticket_type.event_id)
    user_org_id = user.get("orgId")
    if not user_org_id or event.organization_id != user_org_id:
        raise HTTPException(status_code=403, detail="Not authorized")

    # Build update data - only include non-None values
    update_dict = {}
    if input.name is not None:
        update_dict["name"] = input.name
    if input.description is not None:
        update_dict["description"] = input.description
    if input.price is not None:
        update_dict["price"] = input.price
    if input.quantityTotal is not None:
        update_dict["quantity_total"] = input.quantityTotal
    if input.minPerOrder is not None:
        update_dict["min_per_order"] = input.minPerOrder
    if input.maxPerOrder is not None:
        update_dict["max_per_order"] = input.maxPerOrder
    if input.salesStartAt is not None:
        update_dict["sales_start_at"] = input.salesStartAt
    if input.salesEndAt is not None:
        update_dict["sales_end_at"] = input.salesEndAt
    if input.isActive is not None:
        update_dict["is_active"] = input.isActive
    if input.isHidden is not None:
        update_dict["is_hidden"] = input.isHidden
    if input.sortOrder is not None:
        update_dict["sort_order"] = input.sortOrder

    updated = crud.ticket_type.update(db, db_obj=ticket_type, obj_in=update_dict)
    return updated


def archive_ticket_type(ticket_type_id: str, info: Info) -> TicketTypeType:
    """
    Archive a ticket type (organizer only).
    """
    db = info.context.db
    user = info.context.user

    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")

    # Get ticket type
    ticket_type = crud.ticket_type.get(db, id=ticket_type_id)
    if not ticket_type:
        raise HTTPException(status_code=404, detail="Ticket type not found")

    # Verify user has access
    event = crud.event.get(db, id=ticket_type.event_id)
    user_org_id = user.get("orgId")
    if not user_org_id or event.organization_id != user_org_id:
        raise HTTPException(status_code=403, detail="Not authorized")

    archived = crud.ticket_type.archive(db, id=ticket_type_id)
    return archived


# ============================================
# Promo Code Management (Organizer)
# ============================================

def create_promo_code(input: PromoCodeCreateInput, info: Info) -> PromoCodeType:
    """
    Create a new promo code (organizer only).
    """
    db = info.context.db
    user = info.context.user

    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")

    user_org_id = user.get("orgId")
    if not user_org_id:
        raise HTTPException(status_code=403, detail="Not authorized")

    # If event_id is provided, verify it belongs to the organization
    if input.eventId:
        event = crud.event.get(db, id=input.eventId)
        if not event or event.organization_id != user_org_id:
            raise HTTPException(status_code=404, detail="Event not found")

    # Validate discount type (accepts uppercase enum names from frontend)
    try:
        normalized_discount_type = (input.discountType or "").lower()
        discount_type = DiscountType(normalized_discount_type)
    except Exception:
        raise HTTPException(
            status_code=400,
            detail="Invalid discountType. Use 'percentage' or 'fixed'.",
        )
    if discount_type == DiscountType.PERCENTAGE and input.discountValue > 100:
        raise HTTPException(
            status_code=400,
            detail="Percentage discount cannot exceed 100"
        )

    # Create promo code
    promo_create = PromoCodeCreate(
        code=input.code,
        description=input.description,
        discount_type=discount_type,
        discount_value=input.discountValue,
        currency=input.currency,
        applicable_ticket_type_ids=input.applicableTicketTypeIds,
        event_id=input.eventId,
        max_uses=input.maxUses,
        max_uses_per_user=input.maxUsesPerUser,
        minimum_order_amount=input.minimumOrderAmount,
        minimum_tickets=input.minimumTickets,
        min_order_amount=input.minOrderAmount,  # Legacy
        max_discount_amount=input.maxDiscountAmount,
        valid_from=input.validFrom,
        valid_until=input.validUntil,
        is_active=input.isActive,
    )

    promo = crud.promo_code.create_for_organization(
        db, obj_in=promo_create, organization_id=user_org_id
    )
    return promo


def archive_promo_code(promo_code_id: str, info: Info) -> PromoCodeType:
    """
    Deactivate a promo code (organizer only).
    """
    db = info.context.db
    user = info.context.user

    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")

    promo = crud.promo_code.get(db, id=promo_code_id)
    if not promo:
        raise HTTPException(status_code=404, detail="Promo code not found")

    user_org_id = user.get("orgId")
    if not user_org_id or promo.organization_id != user_org_id:
        raise HTTPException(status_code=403, detail="Not authorized")

    # Deactivate the promo code
    promo.is_active = False
    db.add(promo)
    db.commit()
    db.refresh(promo)

    return promo
