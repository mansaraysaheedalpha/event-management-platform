# app/graphql/connect_types.py
"""
Strawberry GraphQL types for Stripe Connect operations.

Types for organizer payment onboarding, account status,
balance, fees, and payout schedules.
"""
import strawberry
from typing import Optional, List
from datetime import datetime
from enum import Enum


# ============================================
# Enums
# ============================================

@strawberry.enum
class PayoutInterval(Enum):
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    MANUAL = "manual"


@strawberry.enum
class FeeAbsorption(Enum):
    ORGANIZER_ABSORBS = "absorb"
    PASS_TO_BUYER = "pass_to_buyer"


@strawberry.enum
class DayOfWeek(Enum):
    MONDAY = "monday"
    TUESDAY = "tuesday"
    WEDNESDAY = "wednesday"
    THURSDAY = "thursday"
    FRIDAY = "friday"
    SATURDAY = "saturday"
    SUNDAY = "sunday"


# ============================================
# Types
# ============================================

@strawberry.type
class ConnectOnboardingResult:
    """Result of creating a Stripe Connect account."""
    onboarding_url: str
    account_connected: bool = True


@strawberry.type
class ConnectOnboardingLink:
    """A Stripe AccountLink for onboarding (short-lived)."""
    url: str
    expires_at: datetime


@strawberry.type
class StripeDashboardLink:
    """A Stripe Express Dashboard login link."""
    url: str


@strawberry.type
class AccountRequirements:
    """Outstanding verification requirements for a connected account."""
    currently_due: List[str]
    eventually_due: List[str]
    past_due: List[str]
    disabled_reason: Optional[str]


@strawberry.type
class OrganizationPaymentStatus:
    """Current Stripe Connect status for an organization."""
    is_connected: bool
    charges_enabled: bool
    payouts_enabled: bool
    details_submitted: bool
    verified: bool
    requirements: Optional[AccountRequirements]
    masked_account_id: Optional[str] = None


@strawberry.type
class BalanceAmount:
    """A monetary amount with currency for balance display."""
    amount: int  # in cents
    currency: str


@strawberry.type
class AccountBalance:
    """Connected account balance (available and pending)."""
    available: List[BalanceAmount]
    pending: List[BalanceAmount]


@strawberry.type
class FeeConfiguration:
    """Platform fee configuration for an organization."""
    platform_fee_percent: float
    platform_fee_fixed: int  # in cents
    fee_absorption: FeeAbsorption
    effective_date: Optional[datetime]


@strawberry.type
class PayoutSchedule:
    """Payout schedule for a connected account."""
    interval: PayoutInterval
    weekly_anchor: Optional[str]
    monthly_anchor: Optional[int]


@strawberry.type
class ConnectMutationResult:
    """Generic success/failure result for Connect mutations."""
    success: bool
    message: Optional[str] = None
