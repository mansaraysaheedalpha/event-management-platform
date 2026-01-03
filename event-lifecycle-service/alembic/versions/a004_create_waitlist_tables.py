"""Create session_waitlist and waitlist_events tables

Revision ID: a004_create_waitlist
Revises: a003_create_ad_analytics
Create Date: 2025-12-30

This migration creates tables for Session Waitlist Management:
- session_waitlist: Queue management for full sessions
- waitlist_events: Event log for waitlist activities
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

# revision identifiers, used by Alembic.
revision = 'a004_create_waitlist'
down_revision = 'a4d5af3bc3bb'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create session_waitlist table
    op.create_table(
        'session_waitlist',
        sa.Column('id', sa.String(), primary_key=True),
        sa.Column('session_id', sa.String(), sa.ForeignKey('sessions.id', ondelete='CASCADE'), nullable=False),
        sa.Column('user_id', sa.String(), nullable=False),  # No FK - users table in different database

        # Queue Management
        sa.Column('priority_tier', sa.String(20), nullable=False, server_default='STANDARD'),
        sa.Column('position', sa.Integer(), nullable=False),

        # Status
        sa.Column('status', sa.String(20), nullable=False, server_default='WAITING'),

        # Offer Details
        sa.Column('offer_token', sa.String(512), nullable=True),
        sa.Column('offer_sent_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('offer_expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('offer_responded_at', sa.DateTime(timezone=True), nullable=True),

        # Timestamps
        sa.Column('joined_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('left_at', sa.DateTime(timezone=True), nullable=True),

        # Constraints
        sa.UniqueConstraint('session_id', 'user_id', name='unique_session_user')
    )

    # Add check constraints
    op.create_check_constraint(
        'check_priority_tier',
        'session_waitlist',
        "priority_tier IN ('STANDARD', 'VIP', 'PREMIUM')"
    )

    op.create_check_constraint(
        'check_status',
        'session_waitlist',
        "status IN ('WAITING', 'OFFERED', 'ACCEPTED', 'DECLINED', 'EXPIRED', 'LEFT')"
    )

    # Create indexes for performance
    op.create_index('idx_waitlist_session_status', 'session_waitlist', ['session_id', 'status'])
    op.create_index('idx_waitlist_position', 'session_waitlist', ['session_id', 'priority_tier', 'position'])
    op.create_index(
        'idx_waitlist_offer_expires',
        'session_waitlist',
        ['offer_expires_at'],
        postgresql_where=sa.text("status = 'OFFERED' AND offer_expires_at IS NOT NULL")
    )

    # Create waitlist_events table
    op.create_table(
        'waitlist_events',
        sa.Column('id', sa.String(), primary_key=True),
        sa.Column('waitlist_entry_id', sa.String(), sa.ForeignKey('session_waitlist.id'), nullable=False),
        sa.Column('event_type', sa.String(50), nullable=False),
        sa.Column('event_data', JSONB(), nullable=True, server_default=sa.text("'{}'::jsonb")),  # Changed from 'metadata'
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()'))
    )

    # Add check constraint for event_type
    op.create_check_constraint(
        'check_event_type',
        'waitlist_events',
        "event_type IN ('JOINED', 'POSITION_CHANGED', 'OFFERED', 'ACCEPTED', 'DECLINED', 'EXPIRED', 'LEFT', 'REMOVED')"
    )

    # Create indexes
    op.create_index('idx_waitlist_events_entry', 'waitlist_events', ['waitlist_entry_id'])
    op.create_index('idx_waitlist_events_type', 'waitlist_events', ['event_type', 'created_at'])


def downgrade() -> None:
    # Drop waitlist_events table and its indexes
    op.drop_index('idx_waitlist_events_type', table_name='waitlist_events')
    op.drop_index('idx_waitlist_events_entry', table_name='waitlist_events')
    op.drop_constraint('check_event_type', 'waitlist_events', type_='check')
    op.drop_table('waitlist_events')

    # Drop session_waitlist table and its indexes
    op.drop_index('idx_waitlist_offer_expires', table_name='session_waitlist')
    op.drop_index('idx_waitlist_position', table_name='session_waitlist')
    op.drop_index('idx_waitlist_session_status', table_name='session_waitlist')
    op.drop_constraint('check_status', 'session_waitlist', type_='check')
    op.drop_constraint('check_priority_tier', 'session_waitlist', type_='check')
    op.drop_constraint('unique_session_user', 'session_waitlist', type_='unique')
    op.drop_table('session_waitlist')
