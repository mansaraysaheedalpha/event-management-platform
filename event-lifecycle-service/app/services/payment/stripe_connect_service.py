# app/services/payment/stripe_connect_service.py
"""
Stripe Connect service for managing Express connected accounts.

Handles the full lifecycle of organizer Stripe accounts:
- Account creation and onboarding
- Account status and balance retrieval
- Payout schedule management
- Account deauthorization
- Webhook event processing
"""
import stripe
import uuid
import logging
from typing import Optional, Dict, Any
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.organization_payment_settings import OrganizationPaymentSettings
from app.models.organizer_payout import OrganizerPayout
from .providers.stripe_provider import PaymentError

logger = logging.getLogger(__name__)


class StripeConnectService:
    """
    Manages Stripe Connect Express accounts for organizers.

    SECURITY NOTES:
    - Never expose full connected account IDs to the frontend
    - Always verify webhook signatures
    - Use idempotency keys for all mutations
    """

    def __init__(self):
        """Initialize Stripe Connect service with platform configuration."""
        if not stripe.api_key:
            stripe.api_key = settings.STRIPE_SECRET_KEY

    def _get_org_settings(
        self, organization_id: str, db: Session
    ) -> Optional[OrganizationPaymentSettings]:
        """Query organization_payment_settings by org_id."""
        return (
            db.query(OrganizationPaymentSettings)
            .filter(OrganizationPaymentSettings.organization_id == organization_id)
            .first()
        )

    async def create_connected_account(
        self,
        organization_id: str,
        organization_name: str,
        email: str,
        country: str,
        db: Session,
    ) -> Dict[str, Any]:
        """
        Creates a Stripe Express connected account for an organization.

        Calls: stripe.Account.create(type="express", ...)
        Stores: connected_account_id in organization_payment_settings
        Returns: { account_id, onboarding_url }
        """
        # Check if org already has a connected account
        existing = self._get_org_settings(organization_id, db)
        if existing and existing.connected_account_id and existing.is_active:
            raise PaymentError(
                code="ACCOUNT_EXISTS",
                message="Organization already has a connected Stripe account",
                retryable=False,
            )

        try:
            idempotency_key = f"connect_create_{organization_id}_{uuid.uuid4().hex[:8]}"

            account = stripe.Account.create(
                type="express",
                country=country,
                email=email,
                business_type="company",
                company={"name": organization_name},
                capabilities={
                    "card_payments": {"requested": True},
                    "transfers": {"requested": True},
                },
                metadata={
                    "organization_id": organization_id,
                    "platform": settings.PLATFORM_NAME,
                },
                idempotency_key=idempotency_key,
            )

            # Create or update org payment settings
            if existing:
                existing.connected_account_id = account.id
                existing.country = country
                existing.is_active = True
                existing.charges_enabled = account.charges_enabled
                existing.payouts_enabled = account.payouts_enabled
                existing.details_submitted = account.details_submitted
                existing.deauthorized_at = None
                existing.updated_at = datetime.now(timezone.utc)
                db.add(existing)
            else:
                # Find the default stripe provider
                from app.models.payment_provider import PaymentProvider

                stripe_provider = (
                    db.query(PaymentProvider)
                    .filter(PaymentProvider.code == "stripe")
                    .first()
                )
                if not stripe_provider:
                    raise PaymentError(
                        code="PROVIDER_NOT_FOUND",
                        message="Stripe payment provider not configured",
                        retryable=False,
                    )

                new_settings = OrganizationPaymentSettings(
                    id=f"ops_{uuid.uuid4().hex[:12]}",
                    organization_id=organization_id,
                    provider_id=stripe_provider.id,
                    connected_account_id=account.id,
                    country=country,
                    charges_enabled=account.charges_enabled,
                    payouts_enabled=account.payouts_enabled,
                    details_submitted=account.details_submitted,
                    platform_fee_percent=settings.PLATFORM_FEE_PERCENT,
                    platform_fee_fixed=settings.PLATFORM_FEE_FIXED_CENTS,
                )
                db.add(new_settings)

            db.commit()

            # Generate onboarding link
            frontend_url = settings.FRONTEND_URL
            account_link = stripe.AccountLink.create(
                account=account.id,
                refresh_url=f"{frontend_url}/dashboard/settings/payments/refresh",
                return_url=f"{frontend_url}/dashboard/settings/payments/return",
                type="account_onboarding",
            )

            logger.info(
                f"Created Stripe Connect account {account.id} for org {organization_id}"
            )

            return {
                "account_id": account.id,
                "onboarding_url": account_link.url,
            }

        except stripe.error.InvalidRequestError as e:
            logger.error(f"Invalid request creating Connect account: {e}")
            raise PaymentError(
                code="INVALID_REQUEST",
                message=str(e),
                retryable=False,
            )
        except stripe.error.StripeError as e:
            logger.error(f"Stripe error creating Connect account: {e}")
            raise PaymentError(
                code="PROVIDER_ERROR",
                message="Could not create connected account",
                retryable=True,
            )

    async def create_onboarding_link(
        self,
        organization_id: str,
        refresh_url: str,
        return_url: str,
        db: Session,
    ) -> Dict[str, Any]:
        """
        Generates a Stripe AccountLink for the organizer to complete onboarding.
        Used when: first-time setup OR re-verification needed.

        Returns: { url, expires_at }
        """
        org_settings = self._get_org_settings(organization_id, db)
        if not org_settings or not org_settings.connected_account_id:
            raise PaymentError(
                code="NO_CONNECTED_ACCOUNT",
                message="Organization does not have a connected Stripe account",
                retryable=False,
            )

        try:
            account_link = stripe.AccountLink.create(
                account=org_settings.connected_account_id,
                refresh_url=refresh_url,
                return_url=return_url,
                type="account_onboarding",
            )

            return {
                "url": account_link.url,
                "expires_at": datetime.fromtimestamp(
                    account_link.expires_at, tz=timezone.utc
                ),
            }

        except stripe.error.InvalidRequestError as e:
            logger.error(f"Invalid request creating onboarding link: {e}")
            raise PaymentError(
                code="INVALID_REQUEST",
                message=str(e),
                retryable=False,
            )
        except stripe.error.StripeError as e:
            logger.error(f"Stripe error creating onboarding link: {e}")
            raise PaymentError(
                code="PROVIDER_ERROR",
                message="Could not create onboarding link",
                retryable=True,
            )

    async def create_login_link(
        self,
        organization_id: str,
        db: Session,
    ) -> str:
        """
        Generates a Stripe Express Dashboard login link for the organizer
        to view payouts, balances, and transaction history.

        Returns: dashboard URL
        """
        org_settings = self._get_org_settings(organization_id, db)
        if not org_settings or not org_settings.connected_account_id:
            raise PaymentError(
                code="NO_CONNECTED_ACCOUNT",
                message="Organization does not have a connected Stripe account",
                retryable=False,
            )

        try:
            login_link = stripe.Account.create_login_link(
                org_settings.connected_account_id
            )
            return login_link.url

        except stripe.error.InvalidRequestError as e:
            # Account may not have completed onboarding yet
            logger.error(f"Cannot create login link: {e}")
            raise PaymentError(
                code="ACCOUNT_NOT_READY",
                message="Account must complete onboarding before accessing the dashboard",
                retryable=False,
            )
        except stripe.error.StripeError as e:
            logger.error(f"Stripe error creating login link: {e}")
            raise PaymentError(
                code="PROVIDER_ERROR",
                message="Could not create dashboard link",
                retryable=True,
            )

    async def get_account_status(
        self,
        organization_id: str,
        db: Session,
    ) -> Dict[str, Any]:
        """
        Retrieves the connected account's current status from Stripe API.

        Returns: {
            account_id, charges_enabled, payouts_enabled, details_submitted,
            requirements, verified
        }
        """
        org_settings = self._get_org_settings(organization_id, db)
        if not org_settings or not org_settings.connected_account_id:
            return {
                "is_connected": False,
                "account_id": None,
                "charges_enabled": False,
                "payouts_enabled": False,
                "details_submitted": False,
                "verified": False,
                "requirements": None,
            }

        try:
            account = stripe.Account.retrieve(org_settings.connected_account_id)

            # Sync local state with Stripe
            org_settings.charges_enabled = account.charges_enabled
            org_settings.payouts_enabled = account.payouts_enabled
            org_settings.details_submitted = account.details_submitted

            requirements_data = {}
            if account.requirements:
                requirements_data = {
                    "currently_due": account.requirements.currently_due or [],
                    "eventually_due": account.requirements.eventually_due or [],
                    "past_due": account.requirements.past_due or [],
                    "disabled_reason": account.requirements.disabled_reason,
                }
            org_settings.requirements_json = requirements_data

            # Mark onboarding completed if details are submitted
            if account.details_submitted and not org_settings.onboarding_completed_at:
                org_settings.onboarding_completed_at = datetime.now(timezone.utc)

            # Update verified_at if fully verified
            if account.charges_enabled and account.payouts_enabled:
                if not org_settings.verified_at:
                    org_settings.verified_at = datetime.now(timezone.utc)
            else:
                org_settings.verified_at = None

            org_settings.updated_at = datetime.now(timezone.utc)
            db.add(org_settings)
            db.commit()

            return {
                "is_connected": True,
                "account_id": account.id,
                "charges_enabled": account.charges_enabled,
                "payouts_enabled": account.payouts_enabled,
                "details_submitted": account.details_submitted,
                "verified": account.charges_enabled and account.payouts_enabled,
                "requirements": requirements_data if requirements_data else None,
            }

        except stripe.error.StripeError as e:
            logger.error(f"Stripe error retrieving account status: {e}")
            raise PaymentError(
                code="PROVIDER_ERROR",
                message="Could not retrieve account status",
                retryable=True,
            )

    async def get_account_balance(
        self,
        organization_id: str,
        db: Session,
    ) -> Dict[str, Any]:
        """
        Gets the connected account's balance.

        Calls: stripe.Balance.retrieve(stripe_account=connected_account_id)
        Returns: { available: [...], pending: [...] }
        """
        org_settings = self._get_org_settings(organization_id, db)
        if not org_settings or not org_settings.connected_account_id:
            raise PaymentError(
                code="NO_CONNECTED_ACCOUNT",
                message="Organization does not have a connected Stripe account",
                retryable=False,
            )

        try:
            balance = stripe.Balance.retrieve(
                stripe_account=org_settings.connected_account_id
            )

            available = [
                {"amount": b.amount, "currency": b.currency.upper()}
                for b in balance.available
            ]
            pending = [
                {"amount": b.amount, "currency": b.currency.upper()}
                for b in balance.pending
            ]

            return {
                "available": available,
                "pending": pending,
            }

        except stripe.error.StripeError as e:
            logger.error(f"Stripe error retrieving balance: {e}")
            raise PaymentError(
                code="PROVIDER_ERROR",
                message="Could not retrieve account balance",
                retryable=True,
            )

    async def update_payout_schedule(
        self,
        organization_id: str,
        interval: str,
        weekly_anchor: Optional[str],
        monthly_anchor: Optional[int],
        db: Session,
    ) -> Dict[str, Any]:
        """
        Updates the payout schedule for a connected account.

        Calls: stripe.Account.modify(connected_account_id, settings={payouts: {schedule: {...}}})
        """
        org_settings = self._get_org_settings(organization_id, db)
        if not org_settings or not org_settings.connected_account_id:
            raise PaymentError(
                code="NO_CONNECTED_ACCOUNT",
                message="Organization does not have a connected Stripe account",
                retryable=False,
            )

        try:
            schedule: Dict[str, Any] = {"interval": interval}

            if interval == "weekly" and weekly_anchor:
                schedule["weekly_anchor"] = weekly_anchor
            elif interval == "monthly" and monthly_anchor:
                schedule["monthly_anchor"] = monthly_anchor

            account = stripe.Account.modify(
                org_settings.connected_account_id,
                settings={"payouts": {"schedule": schedule}},
            )

            # Update local state
            payout_settings = account.settings.payouts.schedule
            org_settings.payout_schedule = payout_settings.interval
            org_settings.updated_at = datetime.now(timezone.utc)
            db.add(org_settings)
            db.commit()

            return {
                "interval": payout_settings.interval,
                "weekly_anchor": getattr(payout_settings, "weekly_anchor", None),
                "monthly_anchor": getattr(payout_settings, "monthly_anchor", None),
            }

        except stripe.error.InvalidRequestError as e:
            logger.error(f"Invalid payout schedule request: {e}")
            raise PaymentError(
                code="INVALID_REQUEST",
                message=str(e),
                retryable=False,
            )
        except stripe.error.StripeError as e:
            logger.error(f"Stripe error updating payout schedule: {e}")
            raise PaymentError(
                code="PROVIDER_ERROR",
                message="Could not update payout schedule",
                retryable=True,
            )

    async def deauthorize_account(
        self,
        organization_id: str,
        db: Session,
    ) -> None:
        """
        Disconnects a connected account from the platform.
        Does NOT delete the Stripe account -- organizer keeps it.

        Calls: stripe.OAuth.deauthorize(...)
        Updates: organization_payment_settings.is_active = False
        """
        org_settings = self._get_org_settings(organization_id, db)
        if not org_settings or not org_settings.connected_account_id:
            raise PaymentError(
                code="NO_CONNECTED_ACCOUNT",
                message="Organization does not have a connected Stripe account",
                retryable=False,
            )

        try:
            stripe.OAuth.deauthorize(
                client_id=settings.STRIPE_CONNECT_CLIENT_ID,
                stripe_user_id=org_settings.connected_account_id,
            )

            # Mark as deauthorized
            org_settings.is_active = False
            org_settings.deauthorized_at = datetime.now(timezone.utc)
            org_settings.charges_enabled = False
            org_settings.payouts_enabled = False
            org_settings.verified_at = None
            org_settings.updated_at = datetime.now(timezone.utc)
            db.add(org_settings)
            db.commit()

            logger.info(
                f"Deauthorized Stripe account for org {organization_id}"
            )

        except stripe.error.InvalidRequestError as e:
            logger.error(f"Invalid deauthorize request: {e}")
            # Even if Stripe deauthorize fails, mark locally as inactive
            org_settings.is_active = False
            org_settings.deauthorized_at = datetime.now(timezone.utc)
            org_settings.updated_at = datetime.now(timezone.utc)
            db.add(org_settings)
            db.commit()
        except stripe.error.StripeError as e:
            logger.error(f"Stripe error deauthorizing account: {e}")
            raise PaymentError(
                code="PROVIDER_ERROR",
                message="Could not disconnect account",
                retryable=True,
            )

    async def handle_account_updated(
        self,
        account_data: Dict[str, Any],
        db: Session,
    ) -> None:
        """
        Webhook handler to sync account status when Stripe sends account.updated.

        Updates charges_enabled, payouts_enabled, details_submitted, requirements.
        """
        account_id = account_data.get("id")
        if not account_id:
            logger.warning("account.updated event without account ID")
            return

        org_settings = (
            db.query(OrganizationPaymentSettings)
            .filter(
                OrganizationPaymentSettings.connected_account_id == account_id
            )
            .first()
        )

        if not org_settings:
            logger.warning(f"No org settings found for account {account_id}")
            return

        # Update status fields
        org_settings.charges_enabled = account_data.get("charges_enabled", False)
        org_settings.payouts_enabled = account_data.get("payouts_enabled", False)
        org_settings.details_submitted = account_data.get("details_submitted", False)

        # Update requirements
        requirements = account_data.get("requirements", {})
        if requirements:
            org_settings.requirements_json = {
                "currently_due": requirements.get("currently_due", []),
                "eventually_due": requirements.get("eventually_due", []),
                "past_due": requirements.get("past_due", []),
                "disabled_reason": requirements.get("disabled_reason"),
            }

        # Update onboarding completion
        if account_data.get("details_submitted") and not org_settings.onboarding_completed_at:
            org_settings.onboarding_completed_at = datetime.now(timezone.utc)

        # Update verification
        if account_data.get("charges_enabled") and account_data.get("payouts_enabled"):
            if not org_settings.verified_at:
                org_settings.verified_at = datetime.now(timezone.utc)
        else:
            org_settings.verified_at = None

        org_settings.updated_at = datetime.now(timezone.utc)
        db.add(org_settings)
        db.commit()

        logger.info(
            f"Updated account status for {account_id}: "
            f"charges={org_settings.charges_enabled}, "
            f"payouts={org_settings.payouts_enabled}"
        )

    async def handle_payout_event(
        self,
        payout_data: Dict[str, Any],
        event_type: str,
        db: Session,
    ) -> None:
        """
        Webhook handler for payout.paid and payout.failed events.

        Logs payout information to the organizer_payouts table.
        """
        payout_id = payout_data.get("id")
        account_id = payout_data.get("destination") or payout_data.get("account")

        if not payout_id:
            logger.warning(f"{event_type} event without payout ID")
            return

        # Find the organization for this connected account
        # The account ID comes from the event's account field
        # For Connect events, we need to look at the event metadata
        org_settings = None
        if account_id:
            org_settings = (
                db.query(OrganizationPaymentSettings)
                .filter(
                    OrganizationPaymentSettings.connected_account_id == account_id
                )
                .first()
            )

        organization_id = org_settings.organization_id if org_settings else "unknown"

        # Check if payout already recorded (idempotency)
        existing = (
            db.query(OrganizerPayout)
            .filter(OrganizerPayout.stripe_payout_id == payout_id)
            .first()
        )

        status = "paid" if event_type == "payout.paid" else "failed"
        amount = payout_data.get("amount", 0)
        currency = (payout_data.get("currency") or "usd").upper()
        arrival_date = payout_data.get("arrival_date")
        failure_code = payout_data.get("failure_code")
        failure_message = payout_data.get("failure_message")

        if existing:
            # Update existing record
            existing.status = status
            existing.failure_code = failure_code
            existing.failure_message = failure_message
            existing.updated_at = datetime.now(timezone.utc)
            db.add(existing)
        else:
            # Insert new payout record
            arrival_dt = None
            if arrival_date:
                arrival_dt = datetime.fromtimestamp(arrival_date, tz=timezone.utc)

            payout_record = OrganizerPayout(
                organization_id=organization_id,
                connected_account_id=account_id or "",
                stripe_payout_id=payout_id,
                amount=amount,
                currency=currency,
                status=status,
                arrival_date=arrival_dt,
                failure_code=failure_code,
                failure_message=failure_message,
            )
            db.add(payout_record)

        db.commit()

        logger.info(
            f"Processed {event_type} for payout {payout_id}: "
            f"amount={amount}, status={status}"
        )
