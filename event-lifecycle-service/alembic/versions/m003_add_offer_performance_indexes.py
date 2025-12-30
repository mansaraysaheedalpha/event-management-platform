"""add offer performance indexes

Revision ID: m003
Revises: m002
Create Date: 2025-12-30

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'm003_performance_indexes'
down_revision = 'm002_offer_purchases'
branch_labels = None
depends_on = None


def upgrade():
    """Add performance indexes for offers."""

    # Composite index for common offer listing query
    # Used in: get_multi_by_event with active filtering
    op.create_index(
        'idx_offers_event_active_archived',
        'offers',
        ['event_id', 'is_active', 'is_archived'],
        unique=False
    )

    # Index for active offers with expiration (background task)
    # Used in: auto_expire_offers task
    op.create_index(
        'idx_offers_active_expires',
        'offers',
        ['is_active', 'expires_at'],
        unique=False
    )

    # Note: offer_purchases already has indexes created in m002 migration:
    # - idx_offer_purchases_user
    # - idx_offer_purchases_offer
    # - idx_offer_purchases_status
    # - idx_offer_purchases_purchased_at


def downgrade():
    """Remove performance indexes."""

    op.drop_index('idx_offers_active_expires', table_name='offers')
    op.drop_index('idx_offers_event_active_archived', table_name='offers')
