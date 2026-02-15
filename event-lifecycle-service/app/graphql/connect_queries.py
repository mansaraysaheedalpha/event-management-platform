# app/graphql/connect_queries.py
"""
GraphQL queries for Stripe Connect operations.

These queries handle:
- Organization payment status
- Connected account balance
- Fee configuration
"""
import logging
from strawberry.types import Info
from fastapi import HTTPException

from ..services.payment.stripe_connect_service import StripeConnectService
from ..services.payment.providers.stripe_provider import PaymentError
from ..core.config import settings
from .connect_types import (
    OrganizationPaymentStatus,
    AccountRequirements,
    AccountBalance,
    BalanceAmount,
    FeeConfiguration,
    FeeAbsorption,
)

logger = logging.getLogger(__name__)


def _verify_org_access(info: Info, organization_id: str) -> dict:
    """
    Verify that the current user is OWNER or ADMIN of the specified organization.

    Returns the user dict from context.
    Raises HTTPException if not authorized.
    """
    user = info.context.user
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")

    user_org_id = user.get("orgId")
    user_role = user.get("role")

    if not user_org_id or user_org_id != organization_id:
        raise HTTPException(
            status_code=403,
            detail="Not authorized to view this organization's payment settings"
        )

    if user_role not in ("OWNER", "ADMIN"):
        raise HTTPException(
            status_code=403,
            detail="Only organization owners and admins can view payment settings"
        )

    return user


async def get_organization_payment_status(
    organization_id: str,
    info: Info,
) -> OrganizationPaymentStatus:
    """
    Get organization's Stripe Connect status.
    Auth: OWNER or ADMIN of the organization.
    """
    _verify_org_access(info, organization_id)
    db = info.context.db

    connect_service = StripeConnectService()

    try:
        status = await connect_service.get_account_status(
            organization_id=organization_id,
            db=db,
        )

        requirements = None
        if status.get("requirements"):
            req = status["requirements"]
            requirements = AccountRequirements(
                currently_due=req.get("currently_due", []),
                eventually_due=req.get("eventually_due", []),
                past_due=req.get("past_due", []),
                disabled_reason=req.get("disabled_reason"),
            )

        # Mask account ID — never expose full acct_ ID to frontend
        masked_id = None
        raw_id = status.get("account_id")
        if raw_id and len(raw_id) > 10:
            masked_id = f"{raw_id[:8]}...{raw_id[-4:]}"
        elif raw_id:
            masked_id = "****"

        return OrganizationPaymentStatus(
            is_connected=status["is_connected"],
            masked_account_id=masked_id,
            charges_enabled=status["charges_enabled"],
            payouts_enabled=status["payouts_enabled"],
            details_submitted=status["details_submitted"],
            verified=status["verified"],
            requirements=requirements,
        )

    except PaymentError as e:
        raise HTTPException(status_code=400, detail=e.message)


async def get_organization_balance(
    organization_id: str,
    info: Info,
) -> AccountBalance:
    """
    Get connected account balance.
    Auth: OWNER or ADMIN.
    """
    _verify_org_access(info, organization_id)
    db = info.context.db

    connect_service = StripeConnectService()

    try:
        balance = await connect_service.get_account_balance(
            organization_id=organization_id,
            db=db,
        )

        available = [
            BalanceAmount(amount=b["amount"], currency=b["currency"])
            for b in balance["available"]
        ]
        pending = [
            BalanceAmount(amount=b["amount"], currency=b["currency"])
            for b in balance["pending"]
        ]

        return AccountBalance(
            available=available,
            pending=pending,
        )

    except PaymentError as e:
        raise HTTPException(status_code=400, detail=e.message)


def get_organization_fees(
    organization_id: str,
    info: Info,
) -> FeeConfiguration:
    """
    Get platform fee configuration for an organization.
    Auth: OWNER or ADMIN.
    """
    _verify_org_access(info, organization_id)
    db = info.context.db

    from ..models.organization_payment_settings import OrganizationPaymentSettings

    org_settings = (
        db.query(OrganizationPaymentSettings)
        .filter(OrganizationPaymentSettings.organization_id == organization_id)
        .first()
    )

    if org_settings:
        fee_percent = float(org_settings.platform_fee_percent or settings.PLATFORM_FEE_PERCENT)
        fee_fixed = int(org_settings.platform_fee_fixed or settings.PLATFORM_FEE_FIXED_CENTS)
        fee_absorption_value = org_settings.fee_absorption or "absorb"
        effective_date = org_settings.updated_at
    else:
        fee_percent = settings.PLATFORM_FEE_PERCENT
        fee_fixed = settings.PLATFORM_FEE_FIXED_CENTS
        fee_absorption_value = "absorb"
        effective_date = None

    return FeeConfiguration(
        platform_fee_percent=fee_percent,
        platform_fee_fixed=fee_fixed,
        fee_absorption=FeeAbsorption(fee_absorption_value),
        effective_date=effective_date,
    )
