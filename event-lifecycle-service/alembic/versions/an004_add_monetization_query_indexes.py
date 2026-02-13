"""Add missing indexes for monetization analytics queries

Revision ID: an004_monetization_query_indexes
Revises: an003_add_events_partitioning
Create Date: 2026-02-12

Adds composite indexes required for production query patterns:
- ad_events: (ad_id, event_type, created_at) for analytics aggregation
- monetization_events: (event_id, event_type, created_at) for funnel queries
- offer_purchases: (offer_id, fulfillment_status) for pending fulfillment batches
"""
from alembic import op


# revision identifiers, used by Alembic.
revision = 'an004_monetization_query_indexes'
down_revision = 'an003_add_events_partitioning'
branch_labels = None
depends_on = None


def upgrade():
    """Add composite indexes for monetization query patterns."""

    # Index for ad analytics aggregation queries:
    #   SELECT ... FROM ad_events WHERE ad_id = ? AND event_type = ?
    #   ORDER BY created_at DESC
    op.create_index(
        'idx_ad_events_analytics',
        'ad_events',
        ['ad_id', 'event_type', 'created_at'],
        unique=False,
    )

    # Index for monetization funnel queries:
    #   SELECT ... FROM monetization_events WHERE event_id = ? AND event_type = ?
    #   ORDER BY created_at
    op.create_index(
        'idx_monetization_events_funnel',
        'monetization_events',
        ['event_id', 'event_type', 'created_at'],
        unique=False,
    )

    # Index for batch fulfillment processing:
    #   SELECT ... FROM offer_purchases WHERE offer_id = ?
    #   AND fulfillment_status = 'PENDING'
    op.create_index(
        'idx_offer_purchases_fulfillment',
        'offer_purchases',
        ['offer_id', 'fulfillment_status'],
        unique=False,
    )


def downgrade():
    """Remove monetization query indexes."""

    op.drop_index('idx_offer_purchases_fulfillment', table_name='offer_purchases')
    op.drop_index('idx_monetization_events_funnel', table_name='monetization_events')
    op.drop_index('idx_ad_events_analytics', table_name='ad_events')
