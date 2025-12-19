# app/api/v1/endpoints/webhooks.py
"""
Webhook endpoints for payment providers.

These endpoints handle asynchronous notifications from payment providers
like Stripe to update payment and order status.

SECURITY NOTES:
- Always verify webhook signatures
- Process events idempotently
- Return 200 quickly, process async if needed
- Log all events for audit purposes
"""
import logging
from datetime import datetime, timezone
from fastapi import APIRouter, Request, HTTPException, Depends, Header
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app import crud
from app.schemas.payment import (
    WebhookEventCreate,
    WebhookEventStatus,
    PaymentStatus,
    OrderStatus,
    RefundStatus,
)
from app.services.payment.provider_factory import get_payment_provider
from app.services.payment.provider_interface import WebhookEventType

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/stripe")
async def stripe_webhook(
    request: Request,
    stripe_signature: str = Header(None, alias="Stripe-Signature"),
    db: Session = Depends(get_db),
):
    """
    Handle Stripe webhook events.

    This endpoint:
    1. Verifies the webhook signature
    2. Stores the event for audit
    3. Processes the event (updates orders, payments, etc.)
    4. Returns 200 to acknowledge receipt

    Stripe will retry on non-2xx responses.
    """
    # Get raw body
    body = await request.body()

    if not stripe_signature:
        logger.warning("Webhook received without Stripe-Signature header")
        raise HTTPException(status_code=400, detail="Missing signature")

    # Get client IP
    client_ip = request.client.host if request.client else None

    try:
        # Get Stripe provider and verify signature
        provider = get_payment_provider("stripe")
        if not provider.verify_webhook_signature(body, stripe_signature):
            logger.warning(f"Invalid webhook signature from {client_ip}")
            raise HTTPException(status_code=400, detail="Invalid signature")

        # Parse the event
        event = provider.parse_webhook_event(body)

        # Check if already processed (idempotency)
        if crud.webhook_event.is_already_processed(
            db, provider_code="stripe", provider_event_id=event.event_id
        ):
            logger.info(f"Event {event.event_id} already processed, skipping")
            return {"status": "already_processed"}

        # Store the event
        webhook_event_create = WebhookEventCreate(
            provider_code="stripe",
            provider_event_id=event.event_id,
            provider_event_type=event.event_type.value,
            payload=event.raw_payload,
            signature_verified=True,
            ip_address=client_ip,
        )
        webhook_event = crud.webhook_event.upsert_event(db, obj_in=webhook_event_create)

        # Mark as processing
        crud.webhook_event.mark_processing(db, event_id=webhook_event.id)

        try:
            # Process based on event type
            result = await _process_stripe_event(db, event, webhook_event.id)

            # Mark as processed
            crud.webhook_event.mark_processed(
                db,
                event_id=webhook_event.id,
                related_payment_id=result.get("payment_id"),
                related_order_id=result.get("order_id"),
                related_refund_id=result.get("refund_id"),
            )

            return {"status": "processed", "event_id": event.event_id}

        except Exception as e:
            logger.error(f"Error processing webhook event {event.event_id}: {e}")
            crud.webhook_event.mark_failed(
                db, event_id=webhook_event.id, error=str(e)
            )
            # Still return 200 to prevent retries for processing errors
            # The event is stored and can be retried manually or via background job
            return {"status": "processing_error", "event_id": event.event_id}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in Stripe webhook: {e}")
        raise HTTPException(status_code=500, detail="Internal error")


async def _process_stripe_event(db: Session, event, webhook_event_id: str) -> dict:
    """
    Process a Stripe webhook event and update database records.

    Returns dict with related entity IDs for audit linking.
    """
    result = {}

    if event.event_type == WebhookEventType.PAYMENT_INTENT_SUCCEEDED:
        result = await _handle_payment_succeeded(db, event)

    elif event.event_type == WebhookEventType.PAYMENT_INTENT_FAILED:
        result = await _handle_payment_failed(db, event)

    elif event.event_type == WebhookEventType.PAYMENT_INTENT_CANCELLED:
        result = await _handle_payment_cancelled(db, event)

    elif event.event_type == WebhookEventType.CHARGE_REFUNDED:
        result = await _handle_charge_refunded(db, event)

    elif event.event_type == WebhookEventType.REFUND_SUCCEEDED:
        result = await _handle_refund_succeeded(db, event)

    elif event.event_type == WebhookEventType.REFUND_FAILED:
        result = await _handle_refund_failed(db, event)

    else:
        logger.info(f"Unhandled event type: {event.event_type}")

    return result


async def _handle_payment_succeeded(db: Session, event) -> dict:
    """Handle payment_intent.succeeded event."""
    result = {}

    intent_id = event.data.get("paymentIntentId")
    if not intent_id:
        logger.warning("Payment succeeded event without intent ID")
        return result

    # Find the order
    order = crud.order.get_by_payment_intent(db, payment_intent_id=intent_id)
    if not order:
        logger.warning(f"No order found for payment intent {intent_id}")
        return result

    result["order_id"] = order.id

    # Skip if already completed
    if order.status == "completed":
        logger.info(f"Order {order.id} already completed")
        return result

    # Create or update payment record
    existing_payment = crud.payment.get_by_provider_intent_id(
        db, provider_intent_id=intent_id
    )

    if existing_payment:
        crud.payment.update_status(
            db,
            payment_id=existing_payment.id,
            status=PaymentStatus.succeeded,
            payment_method_type=event.data.get("payment_method_type"),
        )
        result["payment_id"] = existing_payment.id
    else:
        from app.schemas.payment import PaymentCreate
        payment_create = PaymentCreate(
            order_id=order.id,
            organization_id=order.organization_id,
            provider_code="stripe",
            provider_payment_id=intent_id,
            provider_intent_id=intent_id,
            status=PaymentStatus.succeeded,
            currency=order.currency,
            amount=order.total_amount,
            net_amount=order.total_amount,
            idempotency_key=f"webhook_{event.event_id}",
        )
        payment = crud.payment.create_payment(db, obj_in=payment_create)
        result["payment_id"] = payment.id

    # Update order status
    crud.order.mark_completed(db, order_id=order.id)

    # Update ticket quantities
    order_with_items = crud.order.get_with_items(db, order_id=order.id)
    for item in order_with_items.items:
        crud.ticket_type.increment_quantity_sold(
            db,
            ticket_type_id=item.ticket_type_id,
            quantity=item.quantity,
        )

    # Increment promo code usage
    if order.promo_code_id:
        crud.promo_code.increment_usage(db, promo_code_id=order.promo_code_id)

    # Log audit
    crud.audit_log.log_action(
        db,
        action="payment.succeeded",
        actor_type="webhook",
        entity_type="order",
        entity_id=order.id,
        organization_id=order.organization_id,
        event_id=order.event_id,
        new_state={"status": "completed", "payment_intent": intent_id},
    )

    logger.info(f"Processed payment succeeded for order {order.id}")
    return result


async def _handle_payment_failed(db: Session, event) -> dict:
    """Handle payment_intent.payment_failed event."""
    result = {}

    intent_id = event.data.get("paymentIntentId")
    if not intent_id:
        return result

    order = crud.order.get_by_payment_intent(db, payment_intent_id=intent_id)
    if not order:
        return result

    result["order_id"] = order.id

    # Update payment record if exists
    existing_payment = crud.payment.get_by_provider_intent_id(
        db, provider_intent_id=intent_id
    )

    if existing_payment:
        crud.payment.update_status(
            db,
            payment_id=existing_payment.id,
            status=PaymentStatus.failed,
            failure_code=event.data.get("failureCode"),
            failure_message=event.data.get("failureMessage"),
        )
        result["payment_id"] = existing_payment.id

    # Log audit
    crud.audit_log.log_action(
        db,
        action="payment.failed",
        actor_type="webhook",
        entity_type="order",
        entity_id=order.id,
        organization_id=order.organization_id,
        event_id=order.event_id,
        new_state={
            "failure_code": event.data.get("failureCode"),
            "failure_message": event.data.get("failureMessage"),
        },
    )

    logger.info(f"Processed payment failed for order {order.id}")
    return result


async def _handle_payment_cancelled(db: Session, event) -> dict:
    """Handle payment_intent.canceled event."""
    result = {}

    intent_id = event.data.get("paymentIntentId")
    if not intent_id:
        return result

    order = crud.order.get_by_payment_intent(db, payment_intent_id=intent_id)
    if not order:
        return result

    result["order_id"] = order.id

    # Only cancel if still pending
    if order.status == "pending":
        crud.order.mark_cancelled(db, order_id=order.id)

        crud.audit_log.log_action(
            db,
            action="order.cancelled",
            actor_type="webhook",
            entity_type="order",
            entity_id=order.id,
            organization_id=order.organization_id,
            event_id=order.event_id,
            previous_state={"status": "pending"},
            new_state={"status": "cancelled"},
        )

    logger.info(f"Processed payment cancelled for order {order.id}")
    return result


async def _handle_charge_refunded(db: Session, event) -> dict:
    """Handle charge.refunded event."""
    result = {}

    intent_id = event.data.get("paymentIntentId")
    if not intent_id:
        return result

    # Find the payment
    payment = crud.payment.get_by_provider_intent_id(db, provider_intent_id=intent_id)
    if not payment:
        return result

    result["payment_id"] = payment.id
    result["order_id"] = payment.order_id

    # Get refund amount from event
    refund_amount = event.data.get("amount", 0)

    # Update payment record
    crud.payment.add_refunded_amount(db, payment_id=payment.id, amount=refund_amount)

    # Update order status
    order = crud.order.get(db, id=payment.order_id)
    if order:
        if payment.amount_refunded >= payment.amount:
            order.status = "refunded"
        else:
            order.status = "partially_refunded"
        db.add(order)
        db.commit()

    logger.info(f"Processed charge refunded for payment {payment.id}")
    return result


async def _handle_refund_succeeded(db: Session, event) -> dict:
    """Handle refund.succeeded event."""
    result = {}

    refund_id = event.data.get("refundId")
    if not refund_id:
        return result

    # Find our refund record by provider refund ID
    refund = crud.refund.get_by_provider_refund_id(db, provider_refund_id=refund_id)
    if not refund:
        return result

    result["refund_id"] = refund.id
    result["order_id"] = refund.order_id

    # Update refund status
    crud.refund.update_status(
        db,
        refund_id=refund.id,
        status=RefundStatus.succeeded,
    )

    logger.info(f"Processed refund succeeded for refund {refund.id}")
    return result


async def _handle_refund_failed(db: Session, event) -> dict:
    """Handle refund.failed event."""
    result = {}

    refund_id = event.data.get("refundId")
    if not refund_id:
        return result

    refund = crud.refund.get_by_provider_refund_id(db, provider_refund_id=refund_id)
    if not refund:
        return result

    result["refund_id"] = refund.id
    result["order_id"] = refund.order_id

    crud.refund.update_status(
        db,
        refund_id=refund.id,
        status=RefundStatus.failed,
        failure_code=event.data.get("failureCode"),
        failure_message=event.data.get("failureMessage"),
    )

    logger.info(f"Processed refund failed for refund {refund.id}")
    return result
