"""Create ad_analytics_daily materialized view

Revision ID: a003_create_ad_analytics
Revises: a002_create_ad_events
Create Date: 2025-12-30

This migration creates the ad_analytics_daily materialized view for:
- Aggregating ad impressions, viewable impressions, and clicks by day
- Calculating CTR (click-through rate)
- Tracking unique users reached
- Enabling fast analytics queries
"""

from alembic import op

# revision identifiers, used by Alembic.
revision = 'a003_create_ad_analytics'
down_revision = 'a002_create_ad_events'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create materialized view for daily ad analytics
    op.execute("""
        CREATE MATERIALIZED VIEW ad_analytics_daily AS
        SELECT
            ad_id,
            DATE(created_at) as date,
            COUNT(*) FILTER (WHERE event_type = 'IMPRESSION') as impressions,
            COUNT(*) FILTER (
                WHERE event_type = 'IMPRESSION'
                AND viewport_percentage >= 50
                AND viewable_duration_ms >= 1000
            ) as viewable_impressions,
            COUNT(*) FILTER (WHERE event_type = 'CLICK') as clicks,
            COUNT(DISTINCT COALESCE(user_id, session_token)) as unique_users,
            ROUND(
                COUNT(*) FILTER (WHERE event_type = 'CLICK')::decimal /
                NULLIF(COUNT(*) FILTER (WHERE event_type = 'IMPRESSION'), 0) * 100,
                4
            ) as ctr_percentage
        FROM ad_events
        GROUP BY ad_id, DATE(created_at);
    """)

    # Create unique index on the materialized view for concurrent refresh
    op.execute("""
        CREATE UNIQUE INDEX idx_ad_analytics_daily_unique
        ON ad_analytics_daily(ad_id, date);
    """)

    # Create additional indexes for common queries
    op.execute("""
        CREATE INDEX idx_ad_analytics_daily_date
        ON ad_analytics_daily(date DESC);
    """)

    op.execute("""
        CREATE INDEX idx_ad_analytics_daily_ad
        ON ad_analytics_daily(ad_id);
    """)


def downgrade() -> None:
    # Drop the materialized view (this will also drop its indexes)
    op.execute("DROP MATERIALIZED VIEW IF EXISTS ad_analytics_daily CASCADE;")
