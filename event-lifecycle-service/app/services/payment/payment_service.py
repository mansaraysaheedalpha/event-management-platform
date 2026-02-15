# app/services/payment/payment_service.py
import logging
import uuid
from typing import Optional, List, Tuple
from datetime import datetime, timezone, timedelta
from sqlalchemy.orm import Session

from app import crud
from app.models.order import Order
from app.models.payment import Payment
from app.models.organization_payment_settings import OrganizationPaymentSettings
from app.schemas.payment import (
    CreateOrderInput,
    OrderCreate,
    OrderStatus,
    PaymentStatus,
    PaymentCreate,
    RefundCreate,
    RefundStatus,
    InitiateRefundInput,
    CheckoutSession,
    PaymentIntentResponse,
    AuditLogCreate,
)
from .provider_interface import (
    CreatePaymentIntentParams,
    CreateRefundParams,
    RefundReason as ProviderRefundReason,
)
from .provider_factory import get_payment_provider, get_provider_for_currency
from .providers.stripe_provider import PaymentError
from .fee_calculator import FeeCalculator, OrderItemData
from app.core.config import settings

logger = logging.getLogger(__name__)

# Order expiry time in minutes
ORDER_EXPIRY_MINUTES = 30

# Module-level fee calculator instance using platform defaults
fee_calculator = FeeCalculator(
    default_percent=settings.PLATFORM_FEE_PERCENT,
    default_fixed_cents=settings.PLATFORM_FEE_FIXED_CENTS,
)


class PaymentService:
    """
    Payment service layer that orchestrates payment operations.

    This service:
    - Creates orders and payment intents
    - Handles payment confirmations
    - Processes refunds
    - Manages order lifecycle
    """

    def __init__(self, db: Session):
        self.db = db

    async def create_checkout_session(
        self,
        *,
        input_data: CreateOrderInput,
        organization_id: str,
        user_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        request_id: Optional[str] = None,
    ) -> CheckoutSession:
        """
        Create a checkout session with order and payment intent.

        This is the main entry point for the checkout flow:
        1. Validate ticket availability
        2. Apply promo code if provided
        3. Create order with items
        4. Create payment intent with provider
        5. Return checkout session for frontend

        Returns:
            CheckoutSession with order and payment intent details
        """
        # Get the event to verify it exists and get its currency
        event = crud.event.get(self.db, id=input_data.event_id)
        if not event:
            raise ValueError("Event not found")

        # Validate and collect ticket types
        items_data = []
        subtotal = 0
        currency = None

        for item in input_data.items:
            ticket_type = crud.ticket_type.get(self.db, id=item.ticket_type_id)
            if not ticket_type:
                raise ValueError(f"Ticket type {item.ticket_type_id} not found")

            # Verify ticket is for this event
            if ticket_type.event_id != input_data.event_id:
                raise ValueError(f"Ticket type does not belong to this event")

            # Check availability
            if not crud.ticket_type.is_available(
                self.db, ticket_type_id=item.ticket_type_id, quantity=item.quantity
            ):
                raise ValueError(f"Ticket type {ticket_type.name} is not available")

            # Validate quantity limits
            if item.quantity < ticket_type.min_per_order:
                raise ValueError(
                    f"Minimum {ticket_type.min_per_order} tickets required for {ticket_type.name}"
                )
            if item.quantity > ticket_type.max_per_order:
                raise ValueError(
                    f"Maximum {ticket_type.max_per_order} tickets allowed for {ticket_type.name}"
                )

            # Set currency from first ticket (all tickets in order must have same currency)
            if currency is None:
                currency = ticket_type.currency
            elif currency != ticket_type.currency:
                raise ValueError("All tickets must have the same currency")

            item_total = ticket_type.price * item.quantity
            subtotal += item_total

            items_data.append({
                "ticket_type": ticket_type,
                "quantity": item.quantity,
                "unit_price": ticket_type.price,
                "total_price": item_total,
            })

        if not currency:
            currency = "USD"  # Default currency

        # Apply promo code if provided
        discount_amount = 0
        promo_code_id = None

        if input_data.promo_code:
            promo = crud.promo_code.get_valid_promo_code(
                self.db,
                organization_id=organization_id,
                code=input_data.promo_code,
                event_id=input_data.event_id,
            )
            if promo:
                discount_amount = promo.calculate_discount(subtotal)
                promo_code_id = promo.id
            else:
                raise ValueError("Invalid or expired promo code")

        # Calculate totals
        total_amount = subtotal - discount_amount

        # Ensure total is at least minimum (50 cents)
        if total_amount < 50 and total_amount > 0:
            raise ValueError("Order total is below minimum amount")

        # --- Stripe Connect gating and fee calculation ---
        org_settings = None
        fee_breakdown = None
        buyer_total = total_amount
        platform_fee_amount = 0
        connected_acct_id = None
        order_fee_absorption = "absorb"

        if total_amount > 0:
            # For paid tickets: check organizer's Stripe Connect status
            org_settings = self.db.query(OrganizationPaymentSettings).filter(
                OrganizationPaymentSettings.organization_id == organization_id,
                OrganizationPaymentSettings.is_active == True,
            ).first()

            if not org_settings or not org_settings.connected_account_id:
                raise ValueError(
                    "This organizer has not connected their payment account. "
                    "Ticket purchases are temporarily unavailable."
                )

            if not org_settings.charges_enabled:
                raise ValueError(
                    "The organizer's payment account is under review. "
                    "Please try again later."
                )

            # Build order item data for fee calculation
            order_item_data = [
                OrderItemData(
                    ticket_type_name=item_data["ticket_type"].name,
                    quantity=item_data["quantity"],
                    unit_price=item_data["unit_price"],
                )
                for item_data in items_data
            ]

            fee_breakdown = fee_calculator.calculate_order_fees(order_item_data, org_settings)
            buyer_total = fee_calculator.calculate_buyer_total(
                subtotal=total_amount,
                platform_fee_total=fee_breakdown.platform_fee_total,
                absorption_model=fee_breakdown.absorption_model,
            )
            platform_fee_amount = fee_breakdown.platform_fee_total
            connected_acct_id = org_settings.connected_account_id
            order_fee_absorption = fee_breakdown.absorption_model

        # Generate order number
        order_id = f"ord_{uuid.uuid4().hex[:12]}"
        order_number = Order.generate_order_number(order_id)

        # Calculate expiry time
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=ORDER_EXPIRY_MINUTES)

        # Determine customer info
        customer_email = input_data.guest_email or ""
        customer_name = f"{input_data.guest_first_name or ''} {input_data.guest_last_name or ''}".strip()

        # Build fee breakdown JSON for storage
        fee_breakdown_json = None
        if fee_breakdown:
            fee_breakdown_json = {
                "platform_fee_total": fee_breakdown.platform_fee_total,
                "fee_percent_used": fee_breakdown.fee_percent_used,
                "fee_fixed_used": fee_breakdown.fee_fixed_used,
                "absorption_model": fee_breakdown.absorption_model,
                "per_item_fees": [
                    {
                        "ticket_type_name": item_fee.ticket_type_name,
                        "quantity": item_fee.quantity,
                        "unit_price": item_fee.unit_price,
                        "fee_per_ticket": item_fee.fee_per_ticket,
                        "fee_subtotal": item_fee.fee_subtotal,
                    }
                    for item_fee in fee_breakdown.per_item_fees
                ],
            }

        # Create order
        order_create = OrderCreate(
            event_id=input_data.event_id,
            currency=currency,
            user_id=user_id,
            guest_email=input_data.guest_email,
            guest_first_name=input_data.guest_first_name,
            guest_last_name=input_data.guest_last_name,
            guest_phone=input_data.guest_phone,
            subtotal=subtotal,
            discount_amount=discount_amount,
            tax_amount=0,  # TODO: Calculate tax if needed
            platform_fee=platform_fee_amount,
            total_amount=buyer_total,
            subtotal_amount=total_amount,
            fee_absorption=order_fee_absorption,
            fee_breakdown_json=fee_breakdown_json,
            connected_account_id=connected_acct_id,
            promo_code_id=promo_code_id,
            expires_at=expires_at,
            ip_address=ip_address,
            user_agent=user_agent,
        )

        order = crud.order.create_order(
            self.db,
            obj_in=order_create,
            organization_id=organization_id,
            order_number=order_number,
            order_id=order_id,
        )

        # Add order items and reserve inventory
        for item_data in items_data:
            crud.order.add_item(
                self.db,
                order_id=order.id,
                ticket_type_id=item_data["ticket_type"].id,
                quantity=item_data["quantity"],
                unit_price=item_data["unit_price"],
                ticket_type_name=item_data["ticket_type"].name,
                ticket_type_description=item_data["ticket_type"].description,
            )
            # Reserve inventory so other buyers see reduced availability
            if not crud.ticket_type.reserve_quantity(
                self.db,
                ticket_type_id=item_data["ticket_type"].id,
                quantity=item_data["quantity"],
            ):
                raise ValueError(f"Ticket type {item_data['ticket_type'].name} is no longer available")

        # Log order creation
        self._log_audit(
            action="order.created",
            actor_type="user" if user_id else "guest",
            actor_id=user_id,
            entity_type="order",
            entity_id=order.id,
            organization_id=organization_id,
            event_id=input_data.event_id,
            request_id=request_id,
            new_state={"status": "pending", "total_amount": buyer_total},
            actor_ip=ip_address,
            actor_user_agent=user_agent,
        )

        # Create payment intent if order has amount
        payment_intent = None
        if buyer_total > 0:
            provider = get_provider_for_currency(currency)
            idempotency_key = f"order_{order.id}_create"

            try:
                intent_params = CreatePaymentIntentParams(
                    order_id=order.id,
                    amount=buyer_total,
                    currency=currency,
                    customer_email=customer_email,
                    customer_name=customer_name or "Guest",
                    description=f"Order {order_number} for {event.name}",
                    metadata={
                        "order_id": order.id,
                        "order_number": order_number,
                        "event_id": input_data.event_id,
                        "organization_id": organization_id,
                    },
                    idempotency_key=idempotency_key,
                    connected_account_id=connected_acct_id,
                    platform_fee_amount=platform_fee_amount if connected_acct_id else None,
                )

                result = await provider.create_payment_intent(intent_params)

                # Update order with payment intent info
                order.payment_provider = provider.code
                order.payment_intent_id = result.intent_id
                self.db.add(order)
                self.db.commit()

                payment_intent = PaymentIntentResponse(
                    intent_id=result.intent_id,
                    client_secret=result.client_secret,
                    publishable_key=provider.get_publishable_key(),
                    expires_at=expires_at,
                )

                # Log payment intent creation
                self._log_audit(
                    action="payment.intent_created",
                    actor_type="system",
                    entity_type="order",
                    entity_id=order.id,
                    organization_id=organization_id,
                    event_id=input_data.event_id,
                    request_id=request_id,
                    new_state={
                        "intent_id": result.intent_id,
                        "provider": provider.code,
                        "connected_account_id": connected_acct_id,
                        "platform_fee": platform_fee_amount,
                    },
                )

            except PaymentError as e:
                logger.error(f"Failed to create payment intent: {e}")
                # Mark order as failed
                order.status = "cancelled"
                self.db.add(order)
                self.db.commit()
                raise ValueError(f"Payment error: {e.message}")

        # Refresh order to get items
        self.db.refresh(order)

        # Build response
        from app.schemas.payment import Order as OrderSchema
        order_schema = OrderSchema.model_validate(order)

        return CheckoutSession(
            order=order_schema,
            payment_intent=payment_intent,
        )

    async def confirm_payment(
        self,
        *,
        order_id: str,
        payment_intent_id: str,
        request_id: Optional[str] = None,
    ) -> Order:
        """
        Confirm a payment after client-side completion.

        This is called after the frontend confirms payment with Stripe.
        Validates the payment status and updates the order.
        """
        order = crud.order.get_with_items(self.db, order_id=order_id)
        if not order:
            raise ValueError("Order not found")

        if order.payment_intent_id != payment_intent_id:
            raise ValueError("Payment intent does not match order")

        if order.status == "completed":
            return order  # Already completed (idempotent)

        if order.status != "pending":
            raise ValueError(f"Order cannot be confirmed: status is {order.status}")

        # Get payment status from provider
        provider = get_payment_provider(order.payment_provider)
        intent_status = await provider.get_payment_intent(payment_intent_id)

        if intent_status.status.value != "succeeded":
            raise ValueError(f"Payment not successful: {intent_status.status.value}")

        # Atomically mark order as completed (C2: prevents race condition
        # when both confirm_payment and webhook fire simultaneously)
        was_transitioned = crud.order.mark_completed_atomic(self.db, order_id=order.id)
        if not was_transitioned:
            # Another path (webhook) already completed this order — return idempotently
            self.db.refresh(order)
            return order

        # Create payment record
        payment_create = PaymentCreate(
            order_id=order.id,
            organization_id=order.organization_id,
            provider_code=order.payment_provider,
            provider_payment_id=payment_intent_id,
            provider_intent_id=payment_intent_id,
            status=PaymentStatus.succeeded,
            currency=order.currency,
            amount=order.total_amount,
            net_amount=order.total_amount,  # Will be updated with actual fee
            payment_method_type=intent_status.payment_method_type,
            payment_method_details=intent_status.payment_method_details,
            idempotency_key=f"payment_{order.id}_{payment_intent_id}",
        )

        payment = crud.payment.create_payment(self.db, obj_in=payment_create)

        # Update ticket quantities
        for item in order.items:
            crud.ticket_type.increment_quantity_sold(
                self.db,
                ticket_type_id=item.ticket_type_id,
                quantity=item.quantity,
            )

        # Increment promo code usage if used
        if order.promo_code_id:
            crud.promo_code.increment_usage(self.db, promo_code_id=order.promo_code_id)

        # Log payment success
        self._log_audit(
            action="payment.succeeded",
            actor_type="webhook",
            entity_type="payment",
            entity_id=payment.id,
            organization_id=order.organization_id,
            event_id=order.event_id,
            request_id=request_id,
            new_state={"status": "succeeded", "amount": order.total_amount},
        )

        self._log_audit(
            action="order.completed",
            actor_type="system",
            entity_type="order",
            entity_id=order.id,
            organization_id=order.organization_id,
            event_id=order.event_id,
            request_id=request_id,
            previous_state={"status": "pending"},
            new_state={"status": "completed"},
        )

        self.db.refresh(order)
        return order

    async def cancel_order(
        self,
        *,
        order_id: str,
        user_id: Optional[str] = None,
        request_id: Optional[str] = None,
    ) -> Order:
        """Cancel a pending order."""
        order = crud.order.get_with_items(self.db, order_id=order_id)
        if not order:
            raise ValueError("Order not found")

        if order.status != "pending":
            raise ValueError(f"Order cannot be cancelled: status is {order.status}")

        # Cancel payment intent if exists
        if order.payment_intent_id and order.payment_provider:
            try:
                provider = get_payment_provider(order.payment_provider)
                await provider.cancel_payment_intent(order.payment_intent_id)
            except Exception as e:
                logger.warning(f"Failed to cancel payment intent: {e}")

        # Release reserved inventory
        for item in order.items:
            crud.ticket_type.release_quantity(
                self.db,
                ticket_type_id=item.ticket_type_id,
                quantity=item.quantity,
            )

        # Mark order as cancelled
        crud.order.mark_cancelled(self.db, order_id=order.id)

        # Log cancellation
        self._log_audit(
            action="order.cancelled",
            actor_type="user" if user_id else "system",
            actor_id=user_id,
            entity_type="order",
            entity_id=order.id,
            organization_id=order.organization_id,
            event_id=order.event_id,
            request_id=request_id,
            previous_state={"status": "pending"},
            new_state={"status": "cancelled"},
        )

        self.db.refresh(order)
        return order

    async def initiate_refund(
        self,
        *,
        input_data: InitiateRefundInput,
        initiated_by_user_id: str,
        request_id: Optional[str] = None,
    ):
        """Initiate a refund for an order."""
        order = crud.order.get_with_items(self.db, order_id=input_data.order_id)
        if not order:
            raise ValueError("Order not found")

        if order.status not in ("completed", "partially_refunded"):
            raise ValueError(f"Order cannot be refunded: status is {order.status}")

        # Get the successful payment
        payment = crud.payment.get_successful_payment(self.db, order_id=order.id)
        if not payment:
            raise ValueError("No successful payment found for this order")

        # Determine refund amount
        refund_amount = input_data.amount or payment.refundable_amount
        if refund_amount <= 0:
            raise ValueError("No refundable amount available")
        if refund_amount > payment.refundable_amount:
            raise ValueError(f"Refund amount exceeds refundable amount ({payment.refundable_amount})")

        # Map reason
        reason_map = {
            "requested_by_customer": ProviderRefundReason.REQUESTED_BY_CUSTOMER,
            "duplicate": ProviderRefundReason.DUPLICATE,
            "fraudulent": ProviderRefundReason.FRAUDULENT,
            "event_cancelled": ProviderRefundReason.EVENT_CANCELLED,
            "other": ProviderRefundReason.OTHER,
        }
        provider_reason = reason_map.get(input_data.reason.value, ProviderRefundReason.OTHER)

        # Create refund record
        idempotency_key = f"refund_{order.id}_{uuid.uuid4().hex[:8]}"
        refund_create = RefundCreate(
            payment_id=payment.id,
            order_id=order.id,
            organization_id=order.organization_id,
            provider_code=payment.provider_code,
            amount=refund_amount,
            currency=payment.currency,
            reason=input_data.reason,
            reason_details=input_data.reason_details,
            initiated_by_user_id=initiated_by_user_id,
            idempotency_key=idempotency_key,
        )

        refund = crud.refund.create_refund(self.db, obj_in=refund_create)

        # Log refund initiation
        self._log_audit(
            action="refund.initiated",
            actor_type="admin",
            actor_id=initiated_by_user_id,
            entity_type="refund",
            entity_id=refund.id,
            organization_id=order.organization_id,
            event_id=order.event_id,
            request_id=request_id,
            new_state={"status": "pending", "amount": refund_amount},
        )

        # Process refund with provider
        try:
            provider = get_payment_provider(payment.provider_code)

            # For Connect orders: refund platform's application fee on full refunds (C6)
            is_full_refund = refund_amount >= payment.refundable_amount
            should_refund_app_fee = (
                is_full_refund and bool(getattr(order, "connected_account_id", None))
            )

            refund_params = CreateRefundParams(
                payment_id=payment.provider_intent_id or payment.provider_payment_id,
                amount=refund_amount,
                reason=provider_reason,
                idempotency_key=idempotency_key,
                refund_application_fee=True if should_refund_app_fee else None,
            )

            result = await provider.create_refund(refund_params)

            # Update refund status
            crud.refund.update_status(
                self.db,
                refund_id=refund.id,
                status=RefundStatus.succeeded if result.status.value == "succeeded" else RefundStatus.pending,
                provider_refund_id=result.refund_id,
            )

            # Update payment refunded amount
            crud.payment.add_refunded_amount(
                self.db, payment_id=payment.id, amount=refund_amount
            )

            # Update order status
            if payment.amount_refunded + refund_amount >= payment.amount:
                order.status = "refunded"
            else:
                order.status = "partially_refunded"
            self.db.add(order)
            self.db.commit()

            # Log refund success
            self._log_audit(
                action="refund.succeeded",
                actor_type="system",
                entity_type="refund",
                entity_id=refund.id,
                organization_id=order.organization_id,
                event_id=order.event_id,
                request_id=request_id,
                new_state={"status": "succeeded", "provider_refund_id": result.refund_id},
            )

            # Send refund confirmation email if refund succeeded immediately
            if result.status.value == "succeeded":
                await self._send_refund_email(order, refund_amount, payment.currency)

        except PaymentError as e:
            logger.error(f"Failed to process refund: {e}")
            crud.refund.update_status(
                self.db,
                refund_id=refund.id,
                status=RefundStatus.failed,
                failure_code=e.code,
                failure_message=e.message,
            )
            raise ValueError(f"Refund failed: {e.message}")

        self.db.refresh(refund)
        return refund

    async def expire_pending_orders(self, limit: int = 100) -> int:
        """Expire pending orders that have passed their expiry time."""
        expired_orders = crud.order.get_expired_pending_orders(self.db, limit=limit)
        count = 0

        for order in expired_orders:
            try:
                # Cancel payment intent if exists
                if order.payment_intent_id and order.payment_provider:
                    try:
                        provider = get_payment_provider(order.payment_provider)
                        await provider.cancel_payment_intent(order.payment_intent_id)
                    except Exception as e:
                        logger.warning(f"Failed to cancel payment intent for order {order.id}: {e}")

                # Release reserved inventory
                order_with_items = crud.order.get_with_items(self.db, order_id=order.id)
                if order_with_items:
                    for item in order_with_items.items:
                        crud.ticket_type.release_quantity(
                            self.db,
                            ticket_type_id=item.ticket_type_id,
                            quantity=item.quantity,
                        )

                crud.order.mark_expired(self.db, order_id=order.id)

                self._log_audit(
                    action="order.expired",
                    actor_type="system",
                    entity_type="order",
                    entity_id=order.id,
                    organization_id=order.organization_id,
                    event_id=order.event_id,
                    previous_state={"status": "pending"},
                    new_state={"status": "expired"},
                )

                count += 1
            except Exception as e:
                logger.error(f"Failed to expire order {order.id}: {e}")

        return count

    async def _send_refund_email(self, order, refund_amount: int, currency: str):
        """Send refund confirmation email to buyer."""
        try:
            from app.core.email import send_refund_confirmation_email
            from app.utils.kafka_helpers import publish_refund_confirmation_email
            from app.utils.user_service import get_user_info_async

            # Get event name
            event = crud.event.get(self.db, id=order.event_id)
            event_name = event.name if event else "Event"

            # Get buyer info
            buyer_email = order.guest_email or ""
            buyer_name = order.customer_name or "Valued Customer"

            if order.user_id and not buyer_email:
                user_info = await get_user_info_async(order.user_id)
                if user_info:
                    buyer_email = user_info.get("email", "")
                    buyer_name = user_info.get("name", buyer_name)

            if not buyer_email:
                return

            logger.info(f"Sending refund_confirmation email for order {order.order_number}")
            kafka_sent = publish_refund_confirmation_email(
                to_email=buyer_email,
                buyer_name=buyer_name,
                event_name=event_name,
                order_number=order.order_number,
                refund_amount_cents=refund_amount,
                currency=currency,
            )
            if not kafka_sent:
                send_refund_confirmation_email(
                    to_email=buyer_email,
                    buyer_name=buyer_name,
                    event_name=event_name,
                    order_number=order.order_number,
                    refund_amount_cents=refund_amount,
                    currency=currency,
                )
        except Exception as e:
            logger.error(f"Error sending refund email: {e}", exc_info=True)

    def _log_audit(
        self,
        *,
        action: str,
        actor_type: str,
        entity_type: str,
        entity_id: str,
        actor_id: Optional[str] = None,
        actor_ip: Optional[str] = None,
        actor_user_agent: Optional[str] = None,
        previous_state: Optional[dict] = None,
        new_state: Optional[dict] = None,
        change_details: Optional[dict] = None,
        organization_id: Optional[str] = None,
        event_id: Optional[str] = None,
        request_id: Optional[str] = None,
    ):
        """Log an action to the audit log."""
        try:
            crud.audit_log.log_action(
                self.db,
                action=action,
                actor_type=actor_type,
                actor_id=actor_id,
                actor_ip=actor_ip,
                actor_user_agent=actor_user_agent,
                entity_type=entity_type,
                entity_id=entity_id,
                previous_state=previous_state,
                new_state=new_state,
                change_details=change_details,
                organization_id=organization_id,
                event_id=event_id,
                request_id=request_id,
            )
        except Exception as e:
            logger.error(f"Failed to log audit action: {e}")
