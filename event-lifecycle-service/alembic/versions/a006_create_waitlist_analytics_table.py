"""Create waitlist_analytics table

Revision ID: a006_create_waitlist_analytics
Revises: a005_create_session_capacity
Create Date: 2026-01-03

This migration creates the waitlist_analytics table for caching
computed analytics metrics for events and sessions.
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'a006_create_waitlist_analytics'
down_revision = 'a005_create_session_capacity'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create waitlist_analytics table
    op.create_table(
        'waitlist_analytics',
        sa.Column('id', sa.String(), primary_key=True),
        sa.Column('event_id', sa.String(), sa.ForeignKey('events.id', ondelete='CASCADE'), nullable=False),
        sa.Column('session_id', sa.String(), sa.ForeignKey('sessions.id', ondelete='CASCADE'), nullable=True),
        sa.Column('metric_name', sa.String(100), nullable=False),
        sa.Column('metric_value', sa.Numeric(), nullable=False),
        sa.Column('calculated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()'))
    )

    # Add unique constraint for metric uniqueness per event/session
    op.create_unique_constraint(
        'unique_event_session_metric',
        'waitlist_analytics',
        ['event_id', 'session_id', 'metric_name']
    )

    # Create indexes for performance
    op.create_index('idx_analytics_event', 'waitlist_analytics', ['event_id'])
    op.create_index('idx_analytics_session', 'waitlist_analytics', ['session_id'])
    op.create_index('idx_analytics_metric_name', 'waitlist_analytics', ['metric_name'])
    op.create_index('idx_analytics_calculated_at', 'waitlist_analytics', ['calculated_at'])


def downgrade() -> None:
    # Drop waitlist_analytics table and its indexes
    op.drop_index('idx_analytics_calculated_at', table_name='waitlist_analytics')
    op.drop_index('idx_analytics_metric_name', table_name='waitlist_analytics')
    op.drop_index('idx_analytics_session', table_name='waitlist_analytics')
    op.drop_index('idx_analytics_event', table_name='waitlist_analytics')
    op.drop_constraint('unique_event_session_metric', 'waitlist_analytics', type_='unique')
    op.drop_table('waitlist_analytics')
