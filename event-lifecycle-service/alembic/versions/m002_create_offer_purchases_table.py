"""Create offer_purchases table

Revision ID: m002_offer_purchases
Revises: m001_enhance_offers
Create Date: 2025-12-30

This migration creates the offer_purchases table for tracking offer sales and fulfillment.
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'm002_offer_purchases'
down_revision = 'm001_enhance_offers'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'offer_purchases',
        sa.Column('id', sa.String(), primary_key=True),
        sa.Column('offer_id', sa.String(), sa.ForeignKey('offers.id', ondelete='CASCADE'), nullable=False),
        sa.Column('user_id', sa.String(), nullable=False),  # Will add FK to users later if needed
        sa.Column('order_id', sa.String(), nullable=True),  # Link to orders table if exists

        # Purchase Details
        sa.Column('quantity', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('unit_price', sa.Float(), nullable=False),
        sa.Column('total_price', sa.Float(), nullable=False),
        sa.Column('currency', sa.String(3), nullable=False, server_default='USD'),

        # Fulfillment
        sa.Column('fulfillment_status', sa.String(50), nullable=False, server_default='PENDING'),
        sa.Column('fulfillment_type', sa.String(50), nullable=True),
        sa.Column('digital_content_url', sa.Text(), nullable=True),
        sa.Column('access_code', sa.String(255), nullable=True),
        sa.Column('tracking_number', sa.String(255), nullable=True),

        # Timestamps
        sa.Column('purchased_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('fulfilled_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('refunded_at', sa.DateTime(timezone=True), nullable=True),
    )

    # Add constraints
    op.create_check_constraint(
        'check_quantity_positive',
        'offer_purchases',
        'quantity > 0'
    )

    op.create_check_constraint(
        'check_fulfillment_status',
        'offer_purchases',
        "fulfillment_status IN ('PENDING', 'PROCESSING', 'FULFILLED', 'FAILED', 'REFUNDED')"
    )

    op.create_check_constraint(
        'check_fulfillment_type',
        'offer_purchases',
        "fulfillment_type IS NULL OR fulfillment_type IN ('DIGITAL', 'PHYSICAL', 'SERVICE', 'TICKET')"
    )

    op.create_check_constraint(
        'check_total_price',
        'offer_purchases',
        'total_price = unit_price * quantity'
    )

    # Create indexes
    op.create_index('idx_offer_purchases_user', 'offer_purchases', ['user_id'])
    op.create_index('idx_offer_purchases_offer', 'offer_purchases', ['offer_id'])
    op.create_index('idx_offer_purchases_order', 'offer_purchases', ['order_id'],
                    postgresql_where=sa.text('order_id IS NOT NULL'))
    op.create_index('idx_offer_purchases_status', 'offer_purchases', ['fulfillment_status'])
    op.create_index('idx_offer_purchases_purchased_at', 'offer_purchases', ['purchased_at'])


def downgrade() -> None:
    op.drop_index('idx_offer_purchases_purchased_at', table_name='offer_purchases')
    op.drop_index('idx_offer_purchases_status', table_name='offer_purchases')
    op.drop_index('idx_offer_purchases_order', table_name='offer_purchases')
    op.drop_index('idx_offer_purchases_offer', table_name='offer_purchases')
    op.drop_index('idx_offer_purchases_user', table_name='offer_purchases')

    op.drop_constraint('check_total_price', 'offer_purchases', type_='check')
    op.drop_constraint('check_fulfillment_type', 'offer_purchases', type_='check')
    op.drop_constraint('check_fulfillment_status', 'offer_purchases', type_='check')
    op.drop_constraint('check_quantity_positive', 'offer_purchases', type_='check')

    op.drop_table('offer_purchases')
