"""Create ticket management tables

Revision ID: t001_ticket_mgmt
Revises: p001_payment_tables
Create Date: 2025-12-19

This migration creates:
- promo_code_usages table
- tickets table
- Adds new columns to ticket_types and promo_codes
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ARRAY


# revision identifiers, used by Alembic.
revision = 't001_ticket_mgmt'
down_revision = 'p001_payment_tables'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ========================================
    # Update ticket_types table
    # ========================================
    op.add_column('ticket_types', sa.Column('organization_id', sa.String(), nullable=True))
    op.add_column('ticket_types', sa.Column('quantity_reserved', sa.Integer(), server_default='0', nullable=False))
    op.add_column('ticket_types', sa.Column('is_hidden', sa.Boolean(), server_default=sa.text('false'), nullable=False))
    op.add_column('ticket_types', sa.Column('created_by', sa.String(), nullable=True))

    # Create index for organization_id
    op.create_index('idx_ticket_types_org', 'ticket_types', ['organization_id'])

    # ========================================
    # Update promo_codes table
    # ========================================
    op.add_column('promo_codes', sa.Column('description', sa.Text(), nullable=True))
    op.add_column('promo_codes', sa.Column('applicable_ticket_type_ids', ARRAY(sa.String()), nullable=True))
    op.add_column('promo_codes', sa.Column('max_uses_per_user', sa.Integer(), server_default='1', nullable=False))
    op.add_column('promo_codes', sa.Column('current_uses', sa.Integer(), server_default='0', nullable=False))
    op.add_column('promo_codes', sa.Column('minimum_order_amount', sa.Integer(), nullable=True))
    op.add_column('promo_codes', sa.Column('minimum_tickets', sa.Integer(), server_default='1', nullable=True))
    op.add_column('promo_codes', sa.Column('created_by', sa.String(), nullable=True))

    # ========================================
    # Create promo_code_usages table
    # ========================================
    op.create_table(
        'promo_code_usages',
        sa.Column('id', sa.String(), primary_key=True),
        sa.Column('promo_code_id', sa.String(), sa.ForeignKey('promo_codes.id', ondelete='CASCADE'), nullable=False),
        sa.Column('order_id', sa.String(), sa.ForeignKey('orders.id', ondelete='CASCADE'), nullable=False),
        sa.Column('user_id', sa.String(), nullable=True),
        sa.Column('guest_email', sa.String(255), nullable=True),
        sa.Column('discount_applied', sa.Integer(), nullable=False),
        sa.Column('used_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        # Either user_id or guest_email must be set
        sa.CheckConstraint('user_id IS NOT NULL OR guest_email IS NOT NULL', name='check_user_or_email')
    )

    # Create indexes for promo_code_usages
    op.create_index('idx_promo_usage_code', 'promo_code_usages', ['promo_code_id'])
    op.create_index('idx_promo_usage_order', 'promo_code_usages', ['order_id'])
    op.create_index('idx_promo_usage_user', 'promo_code_usages', ['promo_code_id', 'user_id'])

    # ========================================
    # Create tickets table
    # ========================================
    op.create_table(
        'tickets',
        sa.Column('id', sa.String(), primary_key=True),
        sa.Column('order_id', sa.String(), sa.ForeignKey('orders.id'), nullable=False),
        sa.Column('order_item_id', sa.String(), sa.ForeignKey('order_items.id'), nullable=False),
        sa.Column('ticket_type_id', sa.String(), sa.ForeignKey('ticket_types.id'), nullable=False),
        sa.Column('event_id', sa.String(), sa.ForeignKey('events.id'), nullable=False),
        sa.Column('user_id', sa.String(), nullable=True),
        sa.Column('attendee_email', sa.String(255), nullable=False),
        sa.Column('attendee_name', sa.String(255), nullable=False),
        sa.Column('ticket_code', sa.String(20), unique=True, nullable=False),
        sa.Column('qr_code_data', sa.Text(), nullable=True),
        sa.Column('status', sa.String(50), server_default='valid', nullable=False),
        sa.Column('checked_in_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('checked_in_by', sa.String(), nullable=True),
        sa.Column('check_in_location', sa.String(255), nullable=True),
        sa.Column('transferred_from_ticket_id', sa.String(), sa.ForeignKey('tickets.id'), nullable=True),
        sa.Column('transferred_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    )

    # Create indexes for tickets
    op.create_index('idx_tickets_order', 'tickets', ['order_id'])
    op.create_index('idx_tickets_event', 'tickets', ['event_id'])
    op.create_index('idx_tickets_user', 'tickets', ['user_id'])
    op.create_index('idx_tickets_code', 'tickets', ['ticket_code'])
    op.create_index('idx_tickets_status', 'tickets', ['event_id', 'status'])
    op.create_index('idx_tickets_ticket_type', 'tickets', ['ticket_type_id'])


def downgrade() -> None:
    # Drop tickets table and indexes
    op.drop_index('idx_tickets_ticket_type')
    op.drop_index('idx_tickets_status')
    op.drop_index('idx_tickets_code')
    op.drop_index('idx_tickets_user')
    op.drop_index('idx_tickets_event')
    op.drop_index('idx_tickets_order')
    op.drop_table('tickets')

    # Drop promo_code_usages table and indexes
    op.drop_index('idx_promo_usage_user')
    op.drop_index('idx_promo_usage_order')
    op.drop_index('idx_promo_usage_code')
    op.drop_table('promo_code_usages')

    # Remove promo_codes new columns
    op.drop_column('promo_codes', 'created_by')
    op.drop_column('promo_codes', 'minimum_tickets')
    op.drop_column('promo_codes', 'minimum_order_amount')
    op.drop_column('promo_codes', 'current_uses')
    op.drop_column('promo_codes', 'max_uses_per_user')
    op.drop_column('promo_codes', 'applicable_ticket_type_ids')
    op.drop_column('promo_codes', 'description')

    # Remove ticket_types new columns and indexes
    op.drop_index('idx_ticket_types_org')
    op.drop_column('ticket_types', 'created_by')
    op.drop_column('ticket_types', 'is_hidden')
    op.drop_column('ticket_types', 'quantity_reserved')
    op.drop_column('ticket_types', 'organization_id')
