# app/graphql/connect_mutations.py
"""
GraphQL mutations for Stripe Connect operations.

These mutations handle:
- Creating Stripe Express connected accounts
- Generating onboarding and dashboard links
- Managing payout schedules
- Updating fee absorption settings
- Disconnecting Stripe accounts
"""
import logging
from typing import Optional
from strawberry.types import Info
from fastapi import HTTPException

from ..services.payment.stripe_connect_service import StripeConnectService
from ..services.payment.providers.stripe_provider import PaymentError
import re
from .connect_types import (
    ConnectOnboardingResult,
    ConnectOnboardingLink,
    StripeDashboardLink,
    PayoutSchedule,
    PayoutInterval,
    DayOfWeek,
    FeeAbsorption,
    ConnectMutationResult,
)

# Valid 2-letter ISO 3166-1 alpha-2 country codes supported by Stripe Connect
_VALID_COUNTRY_RE = re.compile(r"^[A-Z]{2}$")

logger = logging.getLogger(__name__)


def _verify_org_access(info: Info, organization_id: str, require_owner: bool = False) -> dict:
    """
    Verify that the current user is OWNER or ADMIN of the specified organization.

    Args:
        info: GraphQL context
        organization_id: The organization to check access for
        require_owner: If True, only OWNER role is allowed

    Returns:
        The user dict from context

    Raises:
        HTTPException if not authorized
    """
    user = info.context.user
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")

    user_org_id = user.get("orgId")
    user_role = user.get("role")

    if not user_org_id or user_org_id != organization_id:
        raise HTTPException(
            status_code=403,
            detail="Not authorized to manage this organization's payment settings"
        )

    if require_owner and user_role != "OWNER":
        raise HTTPException(
            status_code=403,
            detail="Only organization owners can perform this action"
        )

    if user_role not in ("OWNER", "ADMIN"):
        raise HTTPException(
            status_code=403,
            detail="Only organization owners and admins can manage payment settings"
        )

    return user


async def create_stripe_connect_account(
    organization_id: str,
    info: Info,
    country: Optional[str] = "US",
) -> ConnectOnboardingResult:
    """
    Creates a Stripe Express account and returns onboarding URL.
    Auth: OWNER or ADMIN of the organization.
    """
    user = _verify_org_access(info, organization_id)
    db = info.context.db

    # Validate country code (N8)
    country_upper = (country or "US").upper()
    if not _VALID_COUNTRY_RE.match(country_upper):
        raise HTTPException(status_code=400, detail="Invalid country code. Must be a 2-letter ISO code (e.g., US, GB).")

    connect_service = StripeConnectService()

    try:
        # Get organization details for the account
        user_email = user.get("email", "")
        org_name = user.get("orgName", "Organization")

        result = await connect_service.create_connected_account(
            organization_id=organization_id,
            organization_name=org_name,
            email=user_email,
            country=country or "US",
            db=db,
        )

        return ConnectOnboardingResult(
            onboarding_url=result["onboarding_url"],
            account_connected=True,
        )

    except PaymentError as e:
        raise HTTPException(status_code=400, detail=e.message)


async def create_stripe_onboarding_link(
    organization_id: str,
    info: Info,
) -> ConnectOnboardingLink:
    """
    Generates a new onboarding link (if previous expired or needs re-verification).
    Auth: OWNER or ADMIN.
    """
    _verify_org_access(info, organization_id)
    db = info.context.db

    from ..core.config import settings
    frontend_url = settings.FRONTEND_URL

    connect_service = StripeConnectService()

    try:
        result = await connect_service.create_onboarding_link(
            organization_id=organization_id,
            refresh_url=f"{frontend_url}/dashboard/settings/payments/refresh",
            return_url=f"{frontend_url}/dashboard/settings/payments/return",
            db=db,
        )

        return ConnectOnboardingLink(
            url=result["url"],
            expires_at=result["expires_at"],
        )

    except PaymentError as e:
        raise HTTPException(status_code=400, detail=e.message)


async def create_stripe_dashboard_link(
    organization_id: str,
    info: Info,
) -> StripeDashboardLink:
    """
    Generates a Stripe Express Dashboard login link.
    Auth: OWNER or ADMIN.
    """
    _verify_org_access(info, organization_id)
    db = info.context.db

    connect_service = StripeConnectService()

    try:
        url = await connect_service.create_login_link(
            organization_id=organization_id,
            db=db,
        )

        return StripeDashboardLink(url=url)

    except PaymentError as e:
        raise HTTPException(status_code=400, detail=e.message)


async def update_payout_schedule(
    organization_id: str,
    interval: PayoutInterval,
    info: Info,
    weekly_anchor: Optional[DayOfWeek] = None,
    monthly_anchor: Optional[int] = None,
) -> PayoutSchedule:
    """
    Updates payout schedule preferences.
    Auth: OWNER or ADMIN.
    """
    _verify_org_access(info, organization_id)
    db = info.context.db

    # Validate monthly_anchor (N3): Stripe only accepts 1-28
    if interval == PayoutInterval.MONTHLY and monthly_anchor is not None:
        if monthly_anchor < 1 or monthly_anchor > 28:
            raise HTTPException(
                status_code=400,
                detail="Monthly anchor must be between 1 and 28"
            )

    connect_service = StripeConnectService()

    try:
        result = await connect_service.update_payout_schedule(
            organization_id=organization_id,
            interval=interval.value,
            weekly_anchor=weekly_anchor.value if weekly_anchor else None,
            monthly_anchor=monthly_anchor,
            db=db,
        )

        return PayoutSchedule(
            interval=PayoutInterval(result["interval"]),
            weekly_anchor=result.get("weekly_anchor"),
            monthly_anchor=result.get("monthly_anchor"),
        )

    except PaymentError as e:
        raise HTTPException(status_code=400, detail=e.message)


async def update_fee_absorption(
    organization_id: str,
    fee_absorption: FeeAbsorption,
    info: Info,
) -> bool:
    """
    Update fee absorption setting for an organization.
    Auth: OWNER or ADMIN.
    """
    _verify_org_access(info, organization_id)
    db = info.context.db

    from ..models.organization_payment_settings import OrganizationPaymentSettings
    from datetime import datetime, timezone

    org_settings = (
        db.query(OrganizationPaymentSettings)
        .filter(OrganizationPaymentSettings.organization_id == organization_id)
        .first()
    )

    if not org_settings:
        raise HTTPException(
            status_code=404,
            detail="Organization payment settings not found. Connect Stripe first."
        )

    org_settings.fee_absorption = fee_absorption.value
    org_settings.updated_at = datetime.now(timezone.utc)
    db.add(org_settings)
    db.commit()

    return True


async def disconnect_stripe_account(
    organization_id: str,
    info: Info,
) -> bool:
    """
    Disconnects Stripe account (organizer keeps their Stripe account).
    Auth: OWNER only.
    """
    _verify_org_access(info, organization_id, require_owner=True)
    db = info.context.db

    connect_service = StripeConnectService()

    try:
        await connect_service.deauthorize_account(
            organization_id=organization_id,
            db=db,
        )
        return True

    except PaymentError as e:
        raise HTTPException(status_code=400, detail=e.message)
