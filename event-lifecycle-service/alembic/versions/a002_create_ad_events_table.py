"""Create ad_events table for tracking impressions and clicks

Revision ID: a002_create_ad_events
Revises: a001_enhance_ads
Create Date: 2025-12-30

This migration creates the ad_events table for tracking:
- Ad impressions (views)
- Viewable impressions (IAB standard)
- Ad clicks
- User engagement analytics
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, INET

# revision identifiers, used by Alembic.
revision = 'a002_create_ad_events'
down_revision = 'a001_enhance_ads'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create ad_events table
    op.create_table(
        'ad_events',
        sa.Column('id', sa.String(), primary_key=True),
        sa.Column('ad_id', sa.String(), sa.ForeignKey('ads.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('user_id', sa.String(), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('session_token', sa.String(255), nullable=True),

        # Event classification
        sa.Column('event_type', sa.String(20), nullable=False),
        sa.Column('context', sa.String(255), nullable=True),  # Page URL or session ID where ad was shown

        # Viewability metrics (for impressions)
        sa.Column('viewable_duration_ms', sa.Integer(), nullable=True),
        sa.Column('viewport_percentage', sa.Integer(), nullable=True),

        # Technical data
        sa.Column('user_agent', sa.Text(), nullable=True),
        sa.Column('ip_address', INET(), nullable=True),
        sa.Column('referer', sa.Text(), nullable=True),

        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()'))
    )

    # Add check constraint for event_type
    op.create_check_constraint(
        'check_event_type',
        'ad_events',
        "event_type IN ('IMPRESSION', 'CLICK')"
    )

    # Add check constraint for viewport_percentage range
    op.create_check_constraint(
        'check_viewport_percentage',
        'ad_events',
        'viewport_percentage IS NULL OR (viewport_percentage >= 0 AND viewport_percentage <= 100)'
    )

    # Create indexes for performance
    op.create_index('idx_ad_events_ad_type', 'ad_events', ['ad_id', 'event_type'])
    op.create_index('idx_ad_events_created', 'ad_events', ['created_at'])
    op.create_index('idx_ad_events_user', 'ad_events', ['user_id'], postgresql_where=sa.text('user_id IS NOT NULL'))
    op.create_index('idx_ad_events_session', 'ad_events', ['session_token'], postgresql_where=sa.text('session_token IS NOT NULL'))


def downgrade() -> None:
    # Drop indexes
    op.drop_index('idx_ad_events_session', table_name='ad_events')
    op.drop_index('idx_ad_events_user', table_name='ad_events')
    op.drop_index('idx_ad_events_created', table_name='ad_events')
    op.drop_index('idx_ad_events_ad_type', table_name='ad_events')

    # Drop constraints
    op.drop_constraint('check_viewport_percentage', 'ad_events', type_='check')
    op.drop_constraint('check_event_type', 'ad_events', type_='check')

    # Drop table
    op.drop_table('ad_events')
