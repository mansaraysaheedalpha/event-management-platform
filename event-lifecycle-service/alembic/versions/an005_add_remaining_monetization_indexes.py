"""Add remaining monetization indexes for production query patterns

Revision ID: an005_remaining_monetization_indexes
Revises: an004_monetization_query_indexes
Create Date: 2026-02-12

Adds indexes identified during production readiness audit:
- offers: created_at DESC for listing sort, inventory composite for availability
- ads: GIN indexes on placements and target_sessions ARRAY columns
- session_waitlist: priority_tier standalone + composite with session/status
- offer_purchases: (fulfillment_status, purchased_at) for retry task query
"""
from alembic import op


# revision identifiers, used by Alembic.
revision = 'an005_remaining_monetization_indexes'
down_revision = 'an004_monetization_query_indexes'
branch_labels = None
depends_on = None


def upgrade():
    """Add remaining monetization indexes."""

    # M-DB1: Offers created_at DESC for listing sort
    #   SELECT ... FROM offers WHERE event_id = ? ORDER BY created_at DESC
    op.create_index(
        'idx_offers_created_at_desc',
        'offers',
        ['created_at'],
        unique=False,
        postgresql_using='btree',
        postgresql_ops={'created_at': 'DESC'},
    )

    # M-DB1: Offers inventory composite for availability calculations
    #   WHERE inventory_total IS NOT NULL
    #   AND (inventory_total - inventory_sold - inventory_reserved) > 0
    op.create_index(
        'idx_offers_inventory',
        'offers',
        ['inventory_total', 'inventory_sold', 'inventory_reserved'],
        unique=False,
    )

    # M-DB2: Offer purchases (fulfillment_status, purchased_at) for retry task
    #   WHERE fulfillment_status = 'FAILED' AND purchased_at >= cutoff
    #   Note: standalone fulfillment_status index exists in m002,
    #   composite (offer_id, fulfillment_status) exists in an004.
    #   This composite covers the background retry query pattern.
    op.create_index(
        'idx_offer_purchases_status_purchased',
        'offer_purchases',
        ['fulfillment_status', 'purchased_at'],
        unique=False,
    )

    # M-DB3: GIN index on ads.placements for array containment queries
    #   WHERE placements @> ARRAY['EVENT_HERO']
    op.create_index(
        'idx_ads_placements_gin',
        'ads',
        ['placements'],
        unique=False,
        postgresql_using='gin',
    )

    # M-DB3: GIN index on ads.target_sessions for array containment queries
    #   WHERE target_sessions @> ARRAY['session_123']
    op.create_index(
        'idx_ads_target_sessions_gin',
        'ads',
        ['target_sessions'],
        unique=False,
        postgresql_using='gin',
    )

    # M-DB4: Composite index for waitlist queue ordering queries
    #   WHERE session_id = ? AND status = 'WAITING'
    #   ORDER BY priority_tier, position
    op.create_index(
        'idx_session_waitlist_queue_order',
        'session_waitlist',
        ['session_id', 'status', 'priority_tier', 'position'],
        unique=False,
    )


def downgrade():
    """Remove remaining monetization indexes."""

    op.drop_index('idx_session_waitlist_queue_order', table_name='session_waitlist')
    op.drop_index('idx_ads_target_sessions_gin', table_name='ads')
    op.drop_index('idx_ads_placements_gin', table_name='ads')
    op.drop_index('idx_offer_purchases_status_purchased', table_name='offer_purchases')
    op.drop_index('idx_offers_inventory', table_name='offers')
    op.drop_index('idx_offers_created_at_desc', table_name='offers')
