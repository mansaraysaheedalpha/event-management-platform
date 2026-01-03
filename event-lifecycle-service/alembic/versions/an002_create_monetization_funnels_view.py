"""Create monetization_conversion_funnels materialized view

Revision ID: an002_create_monetization_funnels
Revises: an001_create_monetization_events
Create Date: 2025-12-31

This migration creates the monetization_conversion_funnels materialized view for:
- Offer conversion funnel analysis (view → click → cart → purchase)
- Conversion rate calculations
- Revenue tracking per offer
- Performance optimization for analytics queries
"""

from alembic import op

# revision identifiers, used by Alembic.
revision = 'an002_monetization_funnels'
down_revision = 'an001_monetization_events'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create materialized view for conversion funnels
    op.execute("""
        CREATE MATERIALIZED VIEW monetization_conversion_funnels AS
        WITH offer_funnel AS (
            SELECT
                entity_id as offer_id,
                COUNT(*) FILTER (WHERE event_type = 'OFFER_VIEW') as views,
                COUNT(*) FILTER (WHERE event_type = 'OFFER_CLICK') as clicks,
                COUNT(*) FILTER (WHERE event_type = 'OFFER_ADD_TO_CART') as add_to_cart,
                COUNT(*) FILTER (WHERE event_type = 'OFFER_PURCHASE') as purchases,
                SUM(revenue_cents) FILTER (WHERE event_type = 'OFFER_PURCHASE') as revenue_cents
            FROM monetization_events
            WHERE entity_type = 'OFFER'
            GROUP BY entity_id
        )
        SELECT
            offer_id,
            views,
            clicks,
            add_to_cart,
            purchases,
            COALESCE(revenue_cents, 0) as revenue_cents,
            ROUND((clicks::decimal / NULLIF(views, 0)) * 100, 2) as view_to_click_rate,
            ROUND((add_to_cart::decimal / NULLIF(clicks, 0)) * 100, 2) as click_to_cart_rate,
            ROUND((purchases::decimal / NULLIF(add_to_cart, 0)) * 100, 2) as cart_to_purchase_rate,
            ROUND((purchases::decimal / NULLIF(views, 0)) * 100, 2) as overall_conversion_rate
        FROM offer_funnel;
    """)

    # Create unique index for concurrent refresh
    op.execute("""
        CREATE UNIQUE INDEX idx_monetization_funnels_unique
        ON monetization_conversion_funnels(offer_id);
    """)

    # Create additional indexes for common queries
    op.execute("""
        CREATE INDEX idx_monetization_funnels_revenue
        ON monetization_conversion_funnels(revenue_cents DESC);
    """)

    op.execute("""
        CREATE INDEX idx_monetization_funnels_conversion
        ON monetization_conversion_funnels(overall_conversion_rate DESC);
    """)


def downgrade() -> None:
    op.execute("DROP MATERIALIZED VIEW IF EXISTS monetization_conversion_funnels CASCADE;")
