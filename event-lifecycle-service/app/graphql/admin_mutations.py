# app/graphql/admin_mutations.py
"""
GraphQL mutation resolvers for the Platform Admin Panel.

All mutations require the requesting user to have isPlatformAdmin flag.
Provides fee configuration management for organizations and platform defaults.
"""
import logging
from datetime import datetime, timezone
from strawberry.types import Info
from fastapi import HTTPException

from ..models.organization_payment_settings import OrganizationPaymentSettings
from ..core.config import settings
from .admin_types import DefaultFeeConfig

logger = logging.getLogger(__name__)


def _verify_platform_admin(info: Info) -> dict:
    """
    Verify the requesting user is a platform admin.
    Raises HTTPException if not authorized.
    Returns the user dict.
    """
    user = info.context.user
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")

    is_admin = user.get("isPlatformAdmin", False)
    if not is_admin:
        raise HTTPException(
            status_code=403,
            detail="Platform admin access required"
        )

    return user


def admin_set_organization_fees(
    organization_id: str,
    platform_fee_percent: float,
    platform_fee_fixed: int,
    info: Info,
) -> OrganizationPaymentSettings:
    """
    Set custom fee overrides for a specific organization.
    This allows negotiated enterprise rates for individual organizations.
    """
    _verify_platform_admin(info)
    db = info.context.db

    # Validate inputs
    if platform_fee_percent < 0 or platform_fee_percent > 100:
        raise HTTPException(
            status_code=400,
            detail="Platform fee percent must be between 0 and 100"
        )
    if platform_fee_fixed < 0:
        raise HTTPException(
            status_code=400,
            detail="Platform fee fixed amount must be non-negative"
        )

    # Find or create payment settings for this org
    org_settings = db.query(OrganizationPaymentSettings).filter(
        OrganizationPaymentSettings.organization_id == organization_id,
        OrganizationPaymentSettings.is_active.is_(True),
    ).first()

    if not org_settings:
        raise HTTPException(
            status_code=404,
            detail=f"No payment settings found for organization {organization_id}. "
                   "The organization must connect their Stripe account first."
        )

    # Update fees
    org_settings.platform_fee_percent = platform_fee_percent
    org_settings.platform_fee_fixed = platform_fee_fixed
    org_settings.updated_at = datetime.now(timezone.utc)

    db.add(org_settings)
    db.commit()
    db.refresh(org_settings)

    logger.info(
        f"Admin updated fees for org {organization_id}: "
        f"{platform_fee_percent}% + {platform_fee_fixed} cents"
    )

    return org_settings


def admin_set_default_fees(
    platform_fee_percent: float,
    platform_fee_fixed: int,
    info: Info,
) -> DefaultFeeConfig:
    """
    Update default platform fees.

    Note: In production, default fees are stored in environment variables
    (PLATFORM_FEE_PERCENT and PLATFORM_FEE_FIXED_CENTS). This mutation
    would update a platform_settings table. For now, we validate the inputs
    and return the configuration. The actual env var update would happen
    through a deployment pipeline or config service.
    """
    _verify_platform_admin(info)

    # Validate inputs
    if platform_fee_percent < 0 or platform_fee_percent > 100:
        raise HTTPException(
            status_code=400,
            detail="Platform fee percent must be between 0 and 100"
        )
    if platform_fee_fixed < 0:
        raise HTTPException(
            status_code=400,
            detail="Platform fee fixed amount must be non-negative"
        )

    # In a production system, this would update a platform_settings table
    # or a configuration service. For now, we log the update and return
    # the new configuration.
    logger.info(
        f"Admin set default fees: {platform_fee_percent}% + {platform_fee_fixed} cents"
    )

    return DefaultFeeConfig(
        platform_fee_percent=platform_fee_percent,
        platform_fee_fixed=platform_fee_fixed,
        updated_at=datetime.now(timezone.utc),
    )
