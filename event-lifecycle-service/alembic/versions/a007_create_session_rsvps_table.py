"""Create session_rsvps table for in-person session booking

Revision ID: a007_create_session_rsvps
Revises: a006_create_waitlist_analytics
Create Date: 2026-02-12

Adds the session_rsvps table so attendees can RSVP for individual
in-person sessions with capacity enforcement.
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'a007_create_session_rsvps'
down_revision = 'a006_create_waitlist_analytics'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'session_rsvps',
        sa.Column('id', sa.String(), primary_key=True),
        sa.Column('session_id', sa.String(), sa.ForeignKey('sessions.id', ondelete='CASCADE'), nullable=False),
        sa.Column('user_id', sa.String(), nullable=False),
        sa.Column('event_id', sa.String(), sa.ForeignKey('events.id', ondelete='CASCADE'), nullable=False),
        sa.Column('status', sa.String(20), nullable=False, server_default='CONFIRMED'),
        sa.Column('rsvp_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('cancelled_at', sa.DateTime(timezone=True), nullable=True),
    )

    # Unique constraint: one active RSVP per user per session
    op.create_unique_constraint(
        'unique_session_rsvp_user',
        'session_rsvps',
        ['session_id', 'user_id']
    )

    # Indexes for common query patterns
    op.create_index('idx_session_rsvps_session_id', 'session_rsvps', ['session_id'])
    op.create_index('idx_session_rsvps_user_id', 'session_rsvps', ['user_id'])
    op.create_index('idx_session_rsvps_event_id', 'session_rsvps', ['event_id'])
    op.create_index(
        'idx_session_rsvps_session_status',
        'session_rsvps',
        ['session_id', 'status'],
    )
    op.create_index(
        'idx_session_rsvps_user_event',
        'session_rsvps',
        ['user_id', 'event_id', 'status'],
    )


def downgrade() -> None:
    op.drop_index('idx_session_rsvps_user_event', table_name='session_rsvps')
    op.drop_index('idx_session_rsvps_session_status', table_name='session_rsvps')
    op.drop_index('idx_session_rsvps_event_id', table_name='session_rsvps')
    op.drop_index('idx_session_rsvps_user_id', table_name='session_rsvps')
    op.drop_index('idx_session_rsvps_session_id', table_name='session_rsvps')
    op.drop_constraint('unique_session_rsvp_user', 'session_rsvps', type_='unique')
    op.drop_table('session_rsvps')
