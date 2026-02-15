# app/graphql/admin_queries.py
"""
GraphQL query resolvers for the Platform Admin Panel.

All resolvers require the requesting user to have isPlatformAdmin flag.
Provides platform-wide data aggregation for dashboard, organizations,
transactions, and revenue reporting.
"""
import logging
from typing import Optional
from datetime import datetime, timezone, timedelta
from strawberry.types import Info
from fastapi import HTTPException
from sqlalchemy import func, text, case, distinct

from ..models.order import Order
from ..models.order_item import OrderItem
from ..models.event import Event
from ..models.organization_payment_settings import OrganizationPaymentSettings
from .admin_types import (
    AdminDashboardStats,
    AdminOrganizationSummary,
    PaginatedAdminOrganizations,
    AdminOrganizationDetail,
    AdminTransaction,
    PaginatedTransactions,
    RevenueDataPoint,
    RevenueReport,
    ReportPeriod,
    StripeConnectionStatus,
)

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


def get_admin_dashboard_stats(info: Info) -> AdminDashboardStats:
    """
    Get aggregate dashboard statistics for the platform admin.
    Includes total revenue, GMV, organization counts, ticket sales, etc.
    """
    _verify_platform_admin(info)
    db = info.context.db

    # Total platform fees collected (completed orders)
    total_revenue = db.query(
        func.coalesce(func.sum(Order.platform_fee), 0)
    ).filter(Order.status == "completed").scalar() or 0

    # Total GMV (gross merchandise value from completed orders)
    total_gmv = db.query(
        func.coalesce(func.sum(Order.total_amount), 0)
    ).filter(Order.status == "completed").scalar() or 0

    # Total distinct organizations (from events table)
    total_organizations = db.query(
        func.count(distinct(Event.organization_id))
    ).filter(Event.is_archived.is_(False)).scalar() or 0

    # Connected organizations (with active Stripe Connect)
    connected_organizations = db.query(
        func.count(OrganizationPaymentSettings.id)
    ).filter(
        OrganizationPaymentSettings.is_active.is_(True),
        OrganizationPaymentSettings.connected_account_id.isnot(None),
    ).scalar() or 0

    # Total tickets sold (sum of quantities from completed order items)
    total_tickets_sold = db.query(
        func.coalesce(func.sum(OrderItem.quantity), 0)
    ).join(Order, Order.id == OrderItem.order_id).filter(
        Order.status == "completed"
    ).scalar() or 0

    # Total events
    total_events = db.query(
        func.count(Event.id)
    ).filter(Event.is_archived.is_(False)).scalar() or 0

    # Revenue this month
    now = datetime.now(timezone.utc)
    first_of_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    revenue_this_month = db.query(
        func.coalesce(func.sum(Order.platform_fee), 0)
    ).filter(
        Order.status == "completed",
        Order.completed_at >= first_of_month,
    ).scalar() or 0

    # Revenue last month
    first_of_last_month = (first_of_month - timedelta(days=1)).replace(day=1)
    revenue_last_month = db.query(
        func.coalesce(func.sum(Order.platform_fee), 0)
    ).filter(
        Order.status == "completed",
        Order.completed_at >= first_of_last_month,
        Order.completed_at < first_of_month,
    ).scalar() or 0

    # Growth percent
    growth_percent = 0.0
    if revenue_last_month > 0:
        growth_percent = round(
            ((revenue_this_month - revenue_last_month) / revenue_last_month) * 100, 1
        )

    return AdminDashboardStats(
        total_revenue=int(total_revenue),
        total_gmv=int(total_gmv),
        total_organizations=total_organizations,
        connected_organizations=connected_organizations,
        total_tickets_sold=int(total_tickets_sold),
        total_events=total_events,
        revenue_this_month=int(revenue_this_month),
        revenue_last_month=int(revenue_last_month),
        growth_percent=growth_percent,
    )


def get_admin_organizations(
    info: Info,
    page: int = 1,
    limit: int = 20,
    search: Optional[str] = None,
    stripe_status: Optional[StripeConnectionStatus] = None,
) -> PaginatedAdminOrganizations:
    """
    Get paginated list of organizations with their payment status and metrics.
    Supports search by organization name and filtering by Stripe connection status.
    """
    _verify_platform_admin(info)
    db = info.context.db

    # Get all distinct organization IDs from events
    # We subquery to get org-level aggregates
    org_ids_query = db.query(
        Event.organization_id.label("org_id"),
        func.min(Event.createdAt).label("created_at"),
    ).filter(
        Event.is_archived.is_(False),
    ).group_by(Event.organization_id)

    if search:
        # Escape SQL LIKE wildcards in user input to prevent wildcard injection
        safe_search = search.replace("%", r"\%").replace("_", r"\_")
        org_ids_query = org_ids_query.having(
            Event.organization_id.ilike(f"%{safe_search}%", escape="\\")
        )

    org_ids_subquery = org_ids_query.subquery()

    # Apply stripe status filter
    if stripe_status:
        if stripe_status == StripeConnectionStatus.CONNECTED:
            org_ids_with_status = db.query(org_ids_subquery.c.org_id).outerjoin(
                OrganizationPaymentSettings,
                OrganizationPaymentSettings.organization_id == org_ids_subquery.c.org_id,
            ).filter(
                OrganizationPaymentSettings.connected_account_id.isnot(None),
                OrganizationPaymentSettings.is_active.is_(True),
            )
        elif stripe_status == StripeConnectionStatus.PENDING:
            org_ids_with_status = db.query(org_ids_subquery.c.org_id).outerjoin(
                OrganizationPaymentSettings,
                OrganizationPaymentSettings.organization_id == org_ids_subquery.c.org_id,
            ).filter(
                OrganizationPaymentSettings.connected_account_id.isnot(None),
                OrganizationPaymentSettings.is_active.is_(True),
                OrganizationPaymentSettings.verified_at.is_(None),
            )
        else:  # NOT_CONNECTED
            connected_org_ids = db.query(
                OrganizationPaymentSettings.organization_id
            ).filter(
                OrganizationPaymentSettings.connected_account_id.isnot(None),
                OrganizationPaymentSettings.is_active.is_(True),
            ).subquery()

            org_ids_with_status = db.query(org_ids_subquery.c.org_id).filter(
                org_ids_subquery.c.org_id.notin_(
                    db.query(connected_org_ids.c.organization_id)
                )
            )

        filtered_org_ids = [row[0] for row in org_ids_with_status.all()]
    else:
        filtered_org_ids = [row[0] for row in db.query(org_ids_subquery.c.org_id).all()]

    total = len(filtered_org_ids)
    total_pages = max(1, (total + limit - 1) // limit)

    # Paginate
    offset = (page - 1) * limit
    paginated_org_ids = filtered_org_ids[offset:offset + limit]

    # Build summaries for each org
    items = []
    for org_id in paginated_org_ids:
        # Get payment settings
        settings = db.query(OrganizationPaymentSettings).filter(
            OrganizationPaymentSettings.organization_id == org_id,
            OrganizationPaymentSettings.is_active.is_(True),
        ).first()

        is_connected = bool(settings and settings.connected_account_id)
        charges_enabled = bool(settings and hasattr(settings, 'charges_enabled') and settings.charges_enabled) if settings else False
        payouts_enabled = bool(settings and hasattr(settings, 'payouts_enabled') and settings.payouts_enabled) if settings else False

        # Get revenue stats for this org
        org_revenue = db.query(
            func.coalesce(func.sum(Order.total_amount), 0)
        ).filter(
            Order.organization_id == org_id,
            Order.status == "completed",
        ).scalar() or 0

        org_fees = db.query(
            func.coalesce(func.sum(Order.platform_fee), 0)
        ).filter(
            Order.organization_id == org_id,
            Order.status == "completed",
        ).scalar() or 0

        org_tickets = db.query(
            func.coalesce(func.sum(OrderItem.quantity), 0)
        ).join(Order, Order.id == OrderItem.order_id).filter(
            Order.organization_id == org_id,
            Order.status == "completed",
        ).scalar() or 0

        org_events = db.query(func.count(Event.id)).filter(
            Event.organization_id == org_id,
            Event.is_archived.is_(False),
        ).scalar() or 0

        # Get earliest created_at for this org
        org_created = db.query(func.min(Event.createdAt)).filter(
            Event.organization_id == org_id,
        ).scalar() or datetime.now(timezone.utc)

        items.append(AdminOrganizationSummary(
            id=org_id,
            name=org_id,  # Organization name from org_id (would be enriched from user service)
            is_connected=is_connected,
            charges_enabled=charges_enabled,
            payouts_enabled=payouts_enabled,
            total_revenue=int(org_revenue),
            platform_fees_collected=int(org_fees),
            total_tickets_sold=int(org_tickets),
            total_events=org_events,
            created_at=org_created,
        ))

    return PaginatedAdminOrganizations(
        items=items,
        total=total,
        page=page,
        limit=limit,
        total_pages=total_pages,
    )


def get_admin_organization_detail(
    organization_id: str, info: Info
) -> AdminOrganizationDetail:
    """
    Get detailed information about a specific organization.
    Includes payment settings, fee overrides, and aggregate metrics.
    """
    _verify_platform_admin(info)
    db = info.context.db

    # Get payment settings
    settings = db.query(OrganizationPaymentSettings).filter(
        OrganizationPaymentSettings.organization_id == organization_id,
        OrganizationPaymentSettings.is_active.is_(True),
    ).first()

    is_connected = bool(settings and settings.connected_account_id)
    charges_enabled = bool(settings and hasattr(settings, 'charges_enabled') and settings.charges_enabled) if settings else False
    payouts_enabled = bool(settings and hasattr(settings, 'payouts_enabled') and settings.payouts_enabled) if settings else False
    connected_account_id = None
    if settings and settings.connected_account_id:
        # Mask the account ID for security
        acct_id = settings.connected_account_id
        if len(acct_id) > 10:
            connected_account_id = f"{acct_id[:8]}...{acct_id[-4:]}"
        else:
            connected_account_id = acct_id

    # Fee overrides
    fee_override_percent = None
    fee_override_fixed = None
    uses_default_fees = True
    if settings:
        fee_val = float(settings.platform_fee_percent) if settings.platform_fee_percent else 0.0
        fixed_val = int(settings.platform_fee_fixed) if settings.platform_fee_fixed else 0
        if fee_val > 0 or fixed_val > 0:
            fee_override_percent = fee_val
            fee_override_fixed = fixed_val
            uses_default_fees = False

    # Revenue stats
    total_revenue = db.query(
        func.coalesce(func.sum(Order.total_amount), 0)
    ).filter(
        Order.organization_id == organization_id,
        Order.status == "completed",
    ).scalar() or 0

    platform_fees = db.query(
        func.coalesce(func.sum(Order.platform_fee), 0)
    ).filter(
        Order.organization_id == organization_id,
        Order.status == "completed",
    ).scalar() or 0

    total_tickets = db.query(
        func.coalesce(func.sum(OrderItem.quantity), 0)
    ).join(Order, Order.id == OrderItem.order_id).filter(
        Order.organization_id == organization_id,
        Order.status == "completed",
    ).scalar() or 0

    total_events = db.query(func.count(Event.id)).filter(
        Event.organization_id == organization_id,
        Event.is_archived.is_(False),
    ).scalar() or 0

    return AdminOrganizationDetail(
        id=organization_id,
        name=organization_id,  # Would be enriched from user service
        is_connected=is_connected,
        charges_enabled=charges_enabled,
        payouts_enabled=payouts_enabled,
        connected_account_id=connected_account_id,
        total_revenue=int(total_revenue),
        platform_fees_collected=int(platform_fees),
        total_tickets_sold=int(total_tickets),
        total_events=total_events,
        fee_override_percent=fee_override_percent,
        fee_override_fixed=fee_override_fixed,
        uses_default_fees=uses_default_fees,
    )


def get_admin_transactions(
    info: Info,
    page: int = 1,
    limit: int = 20,
    organization_id: Optional[str] = None,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    status: Optional[str] = None,
) -> PaginatedTransactions:
    """
    Get paginated list of all transactions across the platform.
    Supports filtering by organization, date range, and status.
    """
    _verify_platform_admin(info)
    db = info.context.db

    # Base query
    query = db.query(
        Order.id,
        Order.order_number,
        Order.total_amount,
        Order.platform_fee,
        Order.currency,
        Order.status,
        Order.created_at,
        Order.organization_id,
        Event.name.label("event_name"),
    ).join(Event, Event.id == Order.event_id)

    # Apply filters
    if organization_id:
        query = query.filter(Order.organization_id == organization_id)
    if date_from:
        query = query.filter(Order.created_at >= date_from)
    if date_to:
        query = query.filter(Order.created_at <= date_to)
    if status:
        query = query.filter(Order.status == status)

    # Count total
    count_query = query.with_entities(func.count())
    total = count_query.scalar() or 0

    total_pages = max(1, (total + limit - 1) // limit)

    # Paginate
    offset = (page - 1) * limit
    results = query.order_by(Order.created_at.desc()).offset(offset).limit(limit).all()

    items = [
        AdminTransaction(
            order_id=row.id,
            order_number=row.order_number,
            event_name=row.event_name or "Unknown Event",
            organization_name=row.organization_id,  # Would be enriched from user service
            total_amount=row.total_amount,
            platform_fee=row.platform_fee,
            currency=row.currency,
            status=row.status,
            created_at=row.created_at,
        )
        for row in results
    ]

    return PaginatedTransactions(
        items=items,
        total=total,
        page=page,
        limit=limit,
        total_pages=total_pages,
    )


def get_admin_revenue_report(
    info: Info,
    period: ReportPeriod,
    date_from: datetime,
    date_to: datetime,
) -> RevenueReport:
    """
    Get revenue report with data points aggregated by the specified period.
    Supports daily, weekly, and monthly aggregation.
    """
    _verify_platform_admin(info)
    db = info.context.db

    # Determine the SQL date truncation based on period
    if period == ReportPeriod.DAILY:
        date_trunc = func.date_trunc("day", Order.created_at)
        date_format = "%Y-%m-%d"
    elif period == ReportPeriod.WEEKLY:
        date_trunc = func.date_trunc("week", Order.created_at)
        date_format = "%Y-W%V"
    else:  # MONTHLY
        date_trunc = func.date_trunc("month", Order.created_at)
        date_format = "%Y-%m"

    # Query for aggregated data
    results = db.query(
        date_trunc.label("period_date"),
        func.coalesce(func.sum(Order.total_amount), 0).label("gmv"),
        func.coalesce(func.sum(Order.platform_fee), 0).label("platform_fees"),
        func.count(Order.id).label("order_count"),
    ).filter(
        Order.status == "completed",
        Order.created_at >= date_from,
        Order.created_at <= date_to,
    ).group_by("period_date").order_by("period_date").all()

    data_points = []
    total_gmv = 0
    total_platform_fees = 0
    total_orders = 0

    for row in results:
        period_date = row.period_date
        if period_date:
            if isinstance(period_date, datetime):
                date_str = period_date.strftime(date_format)
            else:
                date_str = str(period_date)
        else:
            date_str = "unknown"

        gmv = int(row.gmv)
        fees = int(row.platform_fees)
        count = int(row.order_count)

        total_gmv += gmv
        total_platform_fees += fees
        total_orders += count

        data_points.append(RevenueDataPoint(
            date=date_str,
            gmv=gmv,
            platform_fees=fees,
            order_count=count,
        ))

    return RevenueReport(
        data_points=data_points,
        total_gmv=total_gmv,
        total_platform_fees=total_platform_fees,
        total_orders=total_orders,
        period=period.value,
    )
