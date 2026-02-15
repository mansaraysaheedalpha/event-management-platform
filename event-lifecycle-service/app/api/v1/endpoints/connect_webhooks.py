# app/api/v1/endpoints/connect_webhooks.py
"""
Webhook endpoints for Stripe Connect events.

These endpoints handle asynchronous notifications from Stripe Connect
for connected account lifecycle events (account status, payouts, etc.).

SECURITY NOTES:
- Always verify webhook signatures using STRIPE_CONNECT_WEBHOOK_SECRET
- Process events idempotently
- Return 200 quickly to prevent Stripe retries
- Log all events for audit purposes
"""
import stripe
import logging
from datetime import datetime, timezone
from fastapi import APIRouter, Request, HTTPException, Depends, Header
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app import crud
from app.core.config import settings
from app.schemas.payment import WebhookEventCreate
from app.services.payment.stripe_connect_service import StripeConnectService
from app.core.email import (
    send_stripe_connected_email,
    send_stripe_restricted_email,
    send_payout_sent_email,
    send_payout_failed_email,
)
from app.utils.kafka_helpers import (
    publish_stripe_connected_email,
    publish_stripe_restricted_email,
    publish_payout_sent_email,
    publish_payout_failed_email,
)
from app.utils.user_service import get_user_info_async

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/stripe-connect")
async def stripe_connect_webhook(
    request: Request,
    stripe_signature: str = Header(None, alias="Stripe-Signature"),
    db: Session = Depends(get_db),
):
    """
    Handle Stripe Connect webhook events.

    This endpoint uses a separate webhook secret (STRIPE_CONNECT_WEBHOOK_SECRET)
    from the main payment webhooks because Connect events are delivered
    to a different webhook endpoint.

    Events handled:
    - account.updated: Sync connected account status
    - account.application.deauthorized: Mark account as disconnected
    - payout.paid: Log successful payout
    - payout.failed: Log failed payout
    - capability.updated: Track capability changes
    """
    # Get raw body
    body = await request.body()

    if not stripe_signature:
        logger.warning("Connect webhook received without Stripe-Signature header")
        raise HTTPException(status_code=400, detail="Missing signature")

    # Verify webhook secret is configured
    webhook_secret = settings.STRIPE_CONNECT_WEBHOOK_SECRET
    if not webhook_secret:
        logger.error("STRIPE_CONNECT_WEBHOOK_SECRET not configured")
        raise HTTPException(status_code=500, detail="Webhook secret not configured")

    # Get client IP
    client_ip = request.client.host if request.client else None

    try:
        # Verify signature and construct event
        try:
            event = stripe.Webhook.construct_event(
                body,
                stripe_signature,
                webhook_secret,
            )
        except stripe.error.SignatureVerificationError:
            logger.warning(f"Invalid Connect webhook signature from {client_ip}")
            raise HTTPException(status_code=400, detail="Invalid signature")
        except ValueError:
            logger.warning("Invalid Connect webhook payload")
            raise HTTPException(status_code=400, detail="Invalid payload")

        # Check if already processed (idempotency)
        if crud.webhook_event.is_already_processed(
            db, provider_code="stripe_connect", provider_event_id=event.id
        ):
            logger.info(f"Connect event {event.id} already processed, skipping")
            return {"status": "already_processed"}

        # Store the event for audit
        webhook_event_create = WebhookEventCreate(
            provider_code="stripe_connect",
            provider_event_id=event.id,
            provider_event_type=event.type,
            payload=event.to_dict(),
            signature_verified=True,
            ip_address=client_ip,
        )
        webhook_event = crud.webhook_event.upsert_event(db, obj_in=webhook_event_create)

        # Mark as processing
        crud.webhook_event.mark_processing(db, event_id=webhook_event.id)

        try:
            # Process based on event type
            connect_service = StripeConnectService()
            data_object = event.data.object

            if event.type == "account.updated":
                await connect_service.handle_account_updated(
                    account_data=data_object,
                    db=db,
                )
                # Trigger email notifications for account status changes
                await _send_account_status_emails(data_object, db)

            elif event.type == "account.application.deauthorized":
                await _handle_account_deauthorized(
                    account_data=data_object,
                    db=db,
                )

            elif event.type in ("payout.paid", "payout.failed"):
                # For Connect events, the account field tells us which connected account
                connected_account_id = event.account
                payout_data = dict(data_object)
                if connected_account_id:
                    payout_data["account"] = connected_account_id

                await connect_service.handle_payout_event(
                    payout_data=payout_data,
                    event_type=event.type,
                    db=db,
                )
                # Trigger payout email notifications
                await _send_payout_emails(payout_data, event.type, db)

            elif event.type == "capability.updated":
                await _handle_capability_updated(
                    capability_data=data_object,
                    db=db,
                )

            else:
                logger.info(f"Unhandled Connect event type: {event.type}")

            # Mark as processed
            crud.webhook_event.mark_processed(
                db,
                event_id=webhook_event.id,
            )

            return {"status": "processed", "event_id": event.id}

        except Exception as e:
            logger.error(f"Error processing Connect webhook event {event.id}: {e}")
            crud.webhook_event.mark_failed(
                db, event_id=webhook_event.id, error=str(e)
            )
            # Still return 200 to prevent retries for processing errors
            return {"status": "processing_error", "event_id": event.id}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in Connect webhook: {e}")
        raise HTTPException(status_code=500, detail="Internal error")


async def _handle_account_deauthorized(
    account_data: dict,
    db: Session,
) -> None:
    """
    Handle account.application.deauthorized event.

    Marks the organization's payment settings as inactive when the
    organizer disconnects from their Stripe dashboard.
    """
    from app.models.organization_payment_settings import OrganizationPaymentSettings

    account_id = account_data.get("id")
    if not account_id:
        logger.warning("Deauthorize event without account ID")
        return

    org_settings = (
        db.query(OrganizationPaymentSettings)
        .filter(
            OrganizationPaymentSettings.connected_account_id == account_id
        )
        .first()
    )

    if not org_settings:
        logger.warning(f"No org settings found for deauthorized account {account_id}")
        return

    org_settings.is_active = False
    org_settings.deauthorized_at = datetime.now(timezone.utc)
    org_settings.charges_enabled = False
    org_settings.payouts_enabled = False
    org_settings.verified_at = None
    org_settings.updated_at = datetime.now(timezone.utc)
    db.add(org_settings)
    db.commit()

    logger.info(
        f"Account {account_id} deauthorized for org {org_settings.organization_id}"
    )


async def _get_org_owner_email_and_name(
    organization_id: str, db: Session
) -> tuple[str, str, str]:
    """
    Get org owner's email, name, and organization name for email notifications.

    Returns (email, name, org_name) tuple.
    Falls back to empty/default values if not available.
    """
    email = ""
    name = "Organizer"
    org_name = organization_id

    try:
        from app.models.event import Event

        # Find an event owned by this org to get the owner_id
        event = (
            db.query(Event)
            .filter(Event.organization_id == organization_id)
            .first()
        )

        if event and event.owner_id:
            user_info = await get_user_info_async(event.owner_id)
            if user_info:
                email = user_info.get("email", "")
                name = user_info.get("name", "Organizer")
                # Use orgName from user service if available
                org_name = user_info.get("orgName", organization_id)
    except Exception as e:
        logger.warning(f"Failed to get org owner info for {organization_id}: {e}")

    return email, name, org_name


async def _send_account_status_emails(account_data: dict, db: Session) -> None:
    """
    Send email notifications based on account status changes.

    Triggers:
    - stripe_connected: When charges_enabled becomes True
    - stripe_restricted: When requirements.past_due has items
    """
    account_id = account_data.get("id", "")
    charges_enabled = account_data.get("charges_enabled", False)
    requirements = account_data.get("requirements", {})
    past_due = requirements.get("past_due", [])

    if not account_id:
        return

    # Find the org settings
    from app.models.organization_payment_settings import OrganizationPaymentSettings

    org_settings = (
        db.query(OrganizationPaymentSettings)
        .filter(
            OrganizationPaymentSettings.connected_account_id == account_id
        )
        .first()
    )

    if not org_settings:
        return

    organization_id = org_settings.organization_id
    email, name, org_name = await _get_org_owner_email_and_name(organization_id, db)

    if not email:
        logger.info(f"No email found for org {organization_id}, skipping notification")
        return

    dashboard_url = f"{settings.FRONTEND_URL}/dashboard/settings/payments"

    # Email trigger: stripe_connected (M7: deduplication via one-time flag)
    # Send ONCE when account first becomes fully verified
    if charges_enabled and org_settings.verified_at:
        # Check if we already sent the connected email (prevents duplicates)
        connected_email_already_sent = bool(
            getattr(org_settings, "connected_email_sent_at", None)
        )
        if not connected_email_already_sent:
            logger.info(f"Sending stripe_connected email for org {organization_id}")
            kafka_sent = publish_stripe_connected_email(
                to_email=email,
                organizer_name=name,
                organization_name=org_name,
                dashboard_url=dashboard_url,
            )
            if not kafka_sent:
                send_stripe_connected_email(
                    to_email=email,
                    organizer_name=name,
                    organization_name=org_name,
                    dashboard_url=dashboard_url,
                )
            # Mark email as sent to prevent re-sending
            org_settings.connected_email_sent_at = datetime.now(timezone.utc)
            db.add(org_settings)
            db.commit()

    # Email trigger: stripe_restricted (M8: only after onboarding completed)
    # Don't spam during initial onboarding when many fields are temporarily past_due
    if past_due and org_settings.details_submitted:
        logger.info(f"Sending stripe_restricted email for org {organization_id}")
        kafka_sent = publish_stripe_restricted_email(
            to_email=email,
            organizer_name=name,
            organization_name=org_name,
            requirements_past_due=past_due,
            resolve_url=dashboard_url,
        )
        if not kafka_sent:
            send_stripe_restricted_email(
                to_email=email,
                organizer_name=name,
                organization_name=org_name,
                requirements_past_due=past_due,
                resolve_url=dashboard_url,
            )


async def _send_payout_emails(payout_data: dict, event_type: str, db: Session) -> None:
    """
    Send email notifications for payout events.

    Triggers:
    - payout_sent: When payout.paid event is received
    - payout_failed: When payout.failed event is received
    """
    account_id = payout_data.get("account", "")
    amount = payout_data.get("amount", 0)
    currency = (payout_data.get("currency") or "usd").upper()

    if not account_id:
        return

    # Find the org settings
    from app.models.organization_payment_settings import OrganizationPaymentSettings

    org_settings = (
        db.query(OrganizationPaymentSettings)
        .filter(
            OrganizationPaymentSettings.connected_account_id == account_id
        )
        .first()
    )

    if not org_settings:
        return

    organization_id = org_settings.organization_id
    email, name, org_name = await _get_org_owner_email_and_name(organization_id, db)

    if not email:
        logger.info(f"No email found for org {organization_id}, skipping payout notification")
        return

    dashboard_url = f"{settings.FRONTEND_URL}/dashboard/settings/payments"

    if event_type == "payout.paid":
        # Format arrival date
        arrival_date_str = ""
        arrival_date_ts = payout_data.get("arrival_date")
        if arrival_date_ts:
            try:
                arrival_dt = datetime.fromtimestamp(arrival_date_ts, tz=timezone.utc)
                arrival_date_str = arrival_dt.strftime("%B %d, %Y")
            except Exception:
                pass

        # Get bank last 4
        bank_last_four = ""
        bank_account = payout_data.get("bank_account") or payout_data.get("destination_details", {})
        if isinstance(bank_account, dict):
            bank_last_four = bank_account.get("last4", "")

        logger.info(f"Sending payout_sent email for org {organization_id}")
        kafka_sent = publish_payout_sent_email(
            to_email=email,
            organizer_name=name,
            payout_amount_cents=amount,
            currency=currency,
            arrival_date=arrival_date_str,
            bank_last_four=bank_last_four,
            stripe_dashboard_url=dashboard_url,
        )
        if not kafka_sent:
            send_payout_sent_email(
                to_email=email,
                organizer_name=name,
                payout_amount_cents=amount,
                currency=currency,
                arrival_date=arrival_date_str,
                bank_last_four=bank_last_four,
                stripe_dashboard_url=dashboard_url,
            )

    elif event_type == "payout.failed":
        failure_code = payout_data.get("failure_code", "")
        failure_message = payout_data.get("failure_message", "")
        failure_display = failure_message or failure_code or "An unexpected error occurred with your payout"

        logger.info(f"Sending payout_failed email for org {organization_id}")
        kafka_sent = publish_payout_failed_email(
            to_email=email,
            organizer_name=name,
            payout_amount_cents=amount,
            currency=currency,
            failure_reason=failure_display,
            stripe_dashboard_url=dashboard_url,
        )
        if not kafka_sent:
            send_payout_failed_email(
                to_email=email,
                organizer_name=name,
                payout_amount_cents=amount,
                currency=currency,
                failure_reason=failure_display,
                stripe_dashboard_url=dashboard_url,
            )


async def _handle_capability_updated(
    capability_data: dict,
    db: Session,
) -> None:
    """
    Handle capability.updated event.

    Tracks changes to capabilities (card_payments, transfers) on connected accounts.
    If a capability becomes inactive, we may need to update charges_enabled/payouts_enabled.
    """
    from app.models.organization_payment_settings import OrganizationPaymentSettings

    account_id = capability_data.get("account")
    capability_id = capability_data.get("id")
    status = capability_data.get("status")

    if not account_id:
        logger.warning("Capability event without account ID")
        return

    logger.info(
        f"Capability {capability_id} updated to {status} for account {account_id}"
    )

    # If a critical capability becomes inactive, update the account status
    if status in ("inactive", "unrequested"):
        org_settings = (
            db.query(OrganizationPaymentSettings)
            .filter(
                OrganizationPaymentSettings.connected_account_id == account_id
            )
            .first()
        )

        if org_settings:
            # Re-fetch the full account to get updated status
            try:
                account = stripe.Account.retrieve(account_id)
                org_settings.charges_enabled = account.charges_enabled
                org_settings.payouts_enabled = account.payouts_enabled
                org_settings.updated_at = datetime.now(timezone.utc)
                db.add(org_settings)
                db.commit()
            except stripe.error.StripeError as e:
                logger.error(
                    f"Error fetching account {account_id} after capability update: {e}"
                )
