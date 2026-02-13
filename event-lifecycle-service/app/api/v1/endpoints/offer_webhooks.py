# app/api/v1/endpoints/offer_webhooks.py
"""
Stripe webhook handlers for offer purchases.
"""
import logging
from fastapi import APIRouter, Depends, HTTPException, status, Request, Header
from sqlalchemy.orm import Session
import stripe

from app.db.session import get_db
from app.crud import crud_offer
from app.crud.crud_offer_purchase import offer_purchase
from app.services.offer_stripe_service import offer_stripe_service
from app.core.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Offer Webhooks"])

# Initialize Stripe
stripe.api_key = settings.STRIPE_SECRET_KEY


@router.post("/stripe")
async def stripe_webhook(
    request: Request,
    db: Session = Depends(get_db),
    stripe_signature: str = Header(None, alias="stripe-signature")
):
    """
    Handle Stripe webhook events for offer purchases.

    Events handled:
    - checkout.session.completed: Payment succeeded, confirm purchase
    - checkout.session.expired: Checkout expired, release inventory
    """
    if not stripe_signature:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing stripe-signature header"
        )

    # Get the raw body
    payload = await request.body()

    try:
        # Verify webhook signature
        event = stripe.Webhook.construct_event(
            payload,
            stripe_signature,
            settings.STRIPE_WEBHOOK_SECRET
        )
    except ValueError:
        logger.error("Invalid payload")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid payload"
        )
    except stripe.error.SignatureVerificationError:
        logger.error("Invalid signature")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid signature"
        )

    # Handle the event
    event_type = event["type"]
    data = event["data"]["object"]

    logger.info(f"Received Stripe webhook: {event_type}")

    if event_type == "checkout.session.completed":
        await handle_checkout_completed(db, data)

    elif event_type == "checkout.session.expired":
        await handle_checkout_expired(db, data)

    return {"status": "success"}


async def handle_checkout_completed(db: Session, session_data: dict):
    """
    Handle successful checkout completion.

    Process:
    1. Verify payment_status is 'paid'
    2. Check idempotency (skip if already processed)
    3. Atomically confirm inventory + create purchase record
    4. Trigger fulfillment
    """
    try:
        session_id = session_data["id"]

        # O6: Verify payment actually succeeded before processing
        payment_status = session_data.get("payment_status")
        if payment_status != "paid":
            logger.warning(
                f"Checkout session {session_id} has payment_status={payment_status}, skipping"
            )
            return

        metadata = session_data.get("metadata", {})

        offer_id = metadata.get("offer_id")
        user_id = metadata.get("user_id")
        quantity = int(metadata.get("quantity", 1))

        if not offer_id or not user_id:
            logger.error(f"Missing metadata in checkout session {session_id}")
            return

        # O3: Check idempotency — skip if this session was already processed.
        # Stripe retries webhooks on failure, so we must not create duplicates.
        existing_purchase = offer_purchase.get_by_order_id(db, order_id=session_id)
        if existing_purchase:
            logger.info(
                f"Webhook already processed for session {session_id}, "
                f"purchase {existing_purchase.id} exists — skipping"
            )
            return

        # Get offer
        offer = crud_offer.offer.get(db, id=offer_id)

        if not offer:
            logger.error(f"Offer {offer_id} not found")
            return

        # O7: Wrap confirm + create in a single transaction so both
        # succeed or both fail — prevents inventory marked sold with
        # no purchase record
        try:
            # Confirm purchase - move inventory from reserved to sold
            # auto_commit=False so both operations are in one transaction
            crud_offer.offer.confirm_purchase(
                db,
                offer_id=offer_id,
                quantity=quantity,
                auto_commit=False
            )

            # Create purchase record
            purchase = offer_purchase.create(
                db,
                offer_id=offer_id,
                user_id=user_id,
                quantity=quantity,
                unit_price=offer.price,
                currency=offer.currency,
                order_id=session_id,
                fulfillment_type=_get_fulfillment_type(offer.offer_type),
                auto_commit=False
            )

            # Single commit for both operations
            db.commit()
        except Exception as tx_err:
            db.rollback()
            logger.error(
                f"Transaction failed for session {session_id}: {str(tx_err)}",
                exc_info=True
            )
            raise

        logger.info(
            f"Created offer purchase {purchase.id} for offer {offer_id}, "
            f"user {user_id}, session {session_id}"
        )

    except Exception as e:
        # M-OBS4: Structured error logging with Stripe context for alerting
        logger.error(
            "Webhook checkout.session.completed FAILED: session_id=%s offer_id=%s user_id=%s error=%s",
            session_data.get("id"),
            session_data.get("metadata", {}).get("offer_id"),
            session_data.get("metadata", {}).get("user_id"),
            str(e),
            exc_info=True,
        )
        # Don't raise exception - we don't want to fail the webhook


async def handle_checkout_expired(db: Session, session_data: dict):
    """
    Handle checkout session expiration.

    Process:
    1. Retrieve checkout session metadata
    2. Release reserved inventory
    """
    try:
        session_id = session_data["id"]
        metadata = session_data.get("metadata", {})

        offer_id = metadata.get("offer_id")
        quantity = int(metadata.get("quantity", 1))

        if not offer_id:
            logger.error(f"Missing metadata in expired session {session_id}")
            return

        # Release reserved inventory
        crud_offer.offer.release_inventory(
            db,
            offer_id=offer_id,
            quantity=quantity
        )

        logger.info(
            f"Released {quantity} reserved inventory for offer {offer_id}, "
            f"session {session_id} expired"
        )

    except Exception as e:
        # M-OBS4: Structured error logging for expired checkout
        logger.error(
            "Webhook checkout.session.expired FAILED: session_id=%s offer_id=%s error=%s",
            session_data.get("id"),
            session_data.get("metadata", {}).get("offer_id"),
            str(e),
            exc_info=True,
        )


def _get_fulfillment_type(offer_type: str) -> str:
    """Map offer type to fulfillment type."""
    mapping = {
        "TICKET_UPGRADE": "TICKET",
        "MERCHANDISE": "PHYSICAL",
        "EXCLUSIVE_CONTENT": "DIGITAL",
        "SERVICE": "SERVICE"
    }
    return mapping.get(offer_type, "DIGITAL")
