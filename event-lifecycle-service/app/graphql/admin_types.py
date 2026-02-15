# app/graphql/admin_types.py
"""
Strawberry GraphQL types for the Platform Admin Panel.

These types support:
- Dashboard statistics
- Organization management
- Transaction listing
- Revenue reporting
- Fee configuration
"""
import strawberry
import enum
from typing import Optional
from datetime import datetime


@strawberry.enum
class ReportPeriod(enum.Enum):
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"


@strawberry.enum
class StripeConnectionStatus(enum.Enum):
    CONNECTED = "connected"
    PENDING = "pending"
    NOT_CONNECTED = "not_connected"


@strawberry.type
class AdminDashboardStats:
    """Platform-wide dashboard statistics."""
    total_revenue: int          # Total platform fees collected (cents)
    total_gmv: int              # Gross merchandise value (cents)
    total_organizations: int
    connected_organizations: int
    total_tickets_sold: int
    total_events: int
    revenue_this_month: int
    revenue_last_month: int
    growth_percent: float


@strawberry.type
class AdminOrganizationSummary:
    """Summary of an organization for the admin organizations list."""
    id: str
    name: str
    is_connected: bool
    charges_enabled: bool
    payouts_enabled: bool
    total_revenue: int
    platform_fees_collected: int
    total_tickets_sold: int
    total_events: int
    created_at: datetime


@strawberry.type
class PaginatedAdminOrganizations:
    """Paginated list of organizations for admin view."""
    items: list[AdminOrganizationSummary]
    total: int
    page: int
    limit: int
    total_pages: int


@strawberry.type
class AdminOrganizationDetail:
    """Detailed view of an organization for admin management."""
    id: str
    name: str
    is_connected: bool
    charges_enabled: bool
    payouts_enabled: bool
    connected_account_id: Optional[str]
    total_revenue: int
    platform_fees_collected: int
    total_tickets_sold: int
    total_events: int
    fee_override_percent: Optional[float]
    fee_override_fixed: Optional[int]
    uses_default_fees: bool


@strawberry.type
class AdminTransaction:
    """A transaction record for the admin transactions table."""
    order_id: str
    order_number: str
    event_name: str
    organization_name: str
    total_amount: int
    platform_fee: int
    currency: str
    status: str
    created_at: datetime


@strawberry.type
class PaginatedTransactions:
    """Paginated list of transactions for admin view."""
    items: list[AdminTransaction]
    total: int
    page: int
    limit: int
    total_pages: int


@strawberry.type
class RevenueDataPoint:
    """A single data point in a revenue report."""
    date: str
    gmv: int
    platform_fees: int
    order_count: int


@strawberry.type
class RevenueReport:
    """Revenue report with aggregated data points."""
    data_points: list[RevenueDataPoint]
    total_gmv: int
    total_platform_fees: int
    total_orders: int
    period: str


@strawberry.type
class DefaultFeeConfig:
    """Default platform fee configuration."""
    platform_fee_percent: float
    platform_fee_fixed: int
    updated_at: datetime


@strawberry.input
class AdminSetOrganizationFeesInput:
    """Input for setting organization-specific fees."""
    organization_id: str
    platform_fee_percent: float
    platform_fee_fixed: int


@strawberry.input
class AdminSetDefaultFeesInput:
    """Input for setting default platform fees."""
    platform_fee_percent: float
    platform_fee_fixed: int
