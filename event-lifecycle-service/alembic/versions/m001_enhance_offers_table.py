"""Enhance offers table with full monetization features

Revision ID: m001_enhance_offers
Revises: o001_fix_offer_archived
Create Date: 2025-12-30

This migration enhances the offers table with:
- Inventory management fields
- Stripe integration fields
- Targeting and placement fields
- Scheduling fields
- Proper constraints and indexes
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, ARRAY


# revision identifiers, used by Alembic.
revision = 'm001_enhance_offers'
down_revision = 'o001_fix_offer_archived'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add new columns to offers table
    op.add_column('offers', sa.Column('inventory_total', sa.Integer(), nullable=True))
    op.add_column('offers', sa.Column('inventory_sold', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('offers', sa.Column('inventory_reserved', sa.Integer(), nullable=False, server_default='0'))

    # Stripe integration
    op.add_column('offers', sa.Column('stripe_product_id', sa.String(255), nullable=True))
    op.add_column('offers', sa.Column('stripe_price_id', sa.String(255), nullable=True))

    # Targeting and placement
    op.add_column('offers', sa.Column('placement', sa.String(50), nullable=False, server_default='IN_EVENT'))
    op.add_column('offers', sa.Column('target_sessions', ARRAY(sa.String()), nullable=True, server_default='{}'))
    op.add_column('offers', sa.Column('target_ticket_tiers', ARRAY(sa.String(50)), nullable=True, server_default='{}'))

    # Scheduling
    op.add_column('offers', sa.Column('starts_at', sa.DateTime(timezone=True), nullable=True, server_default=sa.text('NOW()')))

    # Status
    op.add_column('offers', sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'))

    # Metadata
    op.add_column('offers', sa.Column('metadata', sa.JSON(), nullable=True, server_default='{}'))

    # Timestamps
    op.add_column('offers', sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()')))
    op.add_column('offers', sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()')))

    # Add constraints
    op.create_check_constraint(
        'check_offer_type',
        'offers',
        "offer_type IN ('TICKET_UPGRADE', 'MERCHANDISE', 'EXCLUSIVE_CONTENT', 'SERVICE')"
    )

    op.create_check_constraint(
        'check_placement',
        'offers',
        "placement IN ('CHECKOUT', 'POST_PURCHASE', 'IN_EVENT', 'EMAIL')"
    )

    op.create_check_constraint(
        'check_price_positive',
        'offers',
        'price >= 0'
    )

    op.create_check_constraint(
        'check_original_price',
        'offers',
        'original_price IS NULL OR original_price >= price'
    )

    op.create_check_constraint(
        'check_inventory_total',
        'offers',
        'inventory_total IS NULL OR inventory_total > 0'
    )

    op.create_check_constraint(
        'check_inventory_sold',
        'offers',
        'inventory_sold >= 0'
    )

    op.create_check_constraint(
        'check_inventory_reserved',
        'offers',
        'inventory_reserved >= 0'
    )

    op.create_check_constraint(
        'check_valid_inventory',
        'offers',
        'inventory_total IS NULL OR (inventory_sold + inventory_reserved <= inventory_total)'
    )

    # Add indexes
    op.create_index('idx_offers_event_active', 'offers', ['event_id'],
                    postgresql_where=sa.text('is_archived = false AND is_active = true'))
    op.create_index('idx_offers_placement_active', 'offers', ['placement'],
                    postgresql_where=sa.text('is_active = true'))
    op.create_index('idx_offers_expires_at', 'offers', ['expires_at'],
                    postgresql_where=sa.text('expires_at IS NOT NULL'))
    op.create_index('idx_offers_stripe_product', 'offers', ['stripe_product_id'], unique=True,
                    postgresql_where=sa.text('stripe_product_id IS NOT NULL'))
    op.create_index('idx_offers_stripe_price', 'offers', ['stripe_price_id'], unique=True,
                    postgresql_where=sa.text('stripe_price_id IS NOT NULL'))


def downgrade() -> None:
    # Drop indexes
    op.drop_index('idx_offers_stripe_price', table_name='offers')
    op.drop_index('idx_offers_stripe_product', table_name='offers')
    op.drop_index('idx_offers_expires_at', table_name='offers')
    op.drop_index('idx_offers_placement_active', table_name='offers')
    op.drop_index('idx_offers_event_active', table_name='offers')

    # Drop constraints
    op.drop_constraint('check_valid_inventory', 'offers', type_='check')
    op.drop_constraint('check_inventory_reserved', 'offers', type_='check')
    op.drop_constraint('check_inventory_sold', 'offers', type_='check')
    op.drop_constraint('check_inventory_total', 'offers', type_='check')
    op.drop_constraint('check_original_price', 'offers', type_='check')
    op.drop_constraint('check_price_positive', 'offers', type_='check')
    op.drop_constraint('check_placement', 'offers', type_='check')
    op.drop_constraint('check_offer_type', 'offers', type_='check')

    # Drop columns
    op.drop_column('offers', 'updated_at')
    op.drop_column('offers', 'created_at')
    op.drop_column('offers', 'metadata')
    op.drop_column('offers', 'is_active')
    op.drop_column('offers', 'starts_at')
    op.drop_column('offers', 'target_ticket_tiers')
    op.drop_column('offers', 'target_sessions')
    op.drop_column('offers', 'placement')
    op.drop_column('offers', 'stripe_price_id')
    op.drop_column('offers', 'stripe_product_id')
    op.drop_column('offers', 'inventory_reserved')
    op.drop_column('offers', 'inventory_sold')
    op.drop_column('offers', 'inventory_total')
