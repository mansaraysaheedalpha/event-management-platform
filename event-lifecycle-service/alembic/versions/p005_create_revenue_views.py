"""Create platform revenue materialized view for admin dashboard

Revision ID: p005_revenue_views
Revises: p003_connect_enhance
Create Date: 2026-02-14 10:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "p005_revenue_views"
down_revision: Union[str, None] = "p003_connect_enhance"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create materialized view for daily revenue aggregation.
    # This view pre-computes daily revenue metrics per organization,
    # enabling fast dashboard queries without scanning the full orders table.
    op.execute("""
        CREATE MATERIALIZED VIEW IF NOT EXISTS platform_daily_revenue AS
        SELECT
            DATE(o.created_at) AS date,
            o.organization_id,
            COUNT(*) AS order_count,
            COALESCE(SUM(o.total_amount), 0) AS gmv,
            COALESCE(SUM(o.platform_fee), 0) AS platform_fees,
            COALESCE(SUM(o.total_amount - o.platform_fee), 0) AS organizer_revenue,
            o.currency
        FROM orders o
        WHERE o.status = 'completed'
        GROUP BY DATE(o.created_at), o.organization_id, o.currency
    """)

    # Unique index for efficient upsert during refresh
    op.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS idx_daily_revenue_date_org_currency
        ON platform_daily_revenue(date, organization_id, currency)
    """)

    # Additional indexes for common query patterns
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_daily_revenue_date
        ON platform_daily_revenue(date)
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_daily_revenue_org
        ON platform_daily_revenue(organization_id)
    """)


def downgrade() -> None:
    op.execute("DROP MATERIALIZED VIEW IF EXISTS platform_daily_revenue")
