"""Add virtual event support (Phase 1)

Revision ID: v001_add_virtual_event_support
Revises: a006_create_waitlist_analytics
Create Date: 2026-01-11

This migration adds virtual event support to the Event Dynamics platform:
- Event type (IN_PERSON, VIRTUAL, HYBRID)
- Virtual settings JSONB field for events
- Session type (MAINSTAGE, BREAKOUT, WORKSHOP, NETWORKING, EXPO)
- Virtual session fields (streaming URL, recording URL, room settings)
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'v001_add_virtual_event_support'
down_revision = 'a006_create_waitlist_analytics'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ==== EVENT TABLE CHANGES ====

    # Add event_type column with default IN_PERSON
    op.add_column(
        'events',
        sa.Column(
            'event_type',
            sa.String(),
            nullable=False,
            server_default=sa.text("'IN_PERSON'")
        )
    )

    # Add virtual_settings JSONB column
    op.add_column(
        'events',
        sa.Column(
            'virtual_settings',
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            server_default=sa.text("'{}'::jsonb")
        )
    )

    # Add index on event_type for filtering
    op.create_index('idx_events_event_type', 'events', ['event_type'])

    # ==== SESSION TABLE CHANGES ====

    # Add session_type column with default MAINSTAGE
    op.add_column(
        'sessions',
        sa.Column(
            'session_type',
            sa.String(),
            nullable=False,
            server_default=sa.text("'MAINSTAGE'")
        )
    )

    # Add virtual_room_id column
    op.add_column(
        'sessions',
        sa.Column('virtual_room_id', sa.String(), nullable=True)
    )

    # Add streaming_url column
    op.add_column(
        'sessions',
        sa.Column('streaming_url', sa.String(), nullable=True)
    )

    # Add recording_url column
    op.add_column(
        'sessions',
        sa.Column('recording_url', sa.String(), nullable=True)
    )

    # Add is_recordable column
    op.add_column(
        'sessions',
        sa.Column(
            'is_recordable',
            sa.Boolean(),
            nullable=False,
            server_default=sa.text('true')
        )
    )

    # Add requires_camera column
    op.add_column(
        'sessions',
        sa.Column(
            'requires_camera',
            sa.Boolean(),
            nullable=False,
            server_default=sa.text('false')
        )
    )

    # Add requires_microphone column
    op.add_column(
        'sessions',
        sa.Column(
            'requires_microphone',
            sa.Boolean(),
            nullable=False,
            server_default=sa.text('false')
        )
    )

    # Add max_participants column
    op.add_column(
        'sessions',
        sa.Column('max_participants', sa.Integer(), nullable=True)
    )

    # Add broadcast_only column
    op.add_column(
        'sessions',
        sa.Column(
            'broadcast_only',
            sa.Boolean(),
            nullable=False,
            server_default=sa.text('true')
        )
    )

    # Add index on session_type for filtering
    op.create_index('idx_sessions_session_type', 'sessions', ['session_type'])


def downgrade() -> None:
    # ==== REMOVE SESSION COLUMNS ====
    op.drop_index('idx_sessions_session_type', table_name='sessions')
    op.drop_column('sessions', 'broadcast_only')
    op.drop_column('sessions', 'max_participants')
    op.drop_column('sessions', 'requires_microphone')
    op.drop_column('sessions', 'requires_camera')
    op.drop_column('sessions', 'is_recordable')
    op.drop_column('sessions', 'recording_url')
    op.drop_column('sessions', 'streaming_url')
    op.drop_column('sessions', 'virtual_room_id')
    op.drop_column('sessions', 'session_type')

    # ==== REMOVE EVENT COLUMNS ====
    op.drop_index('idx_events_event_type', table_name='events')
    op.drop_column('events', 'virtual_settings')
    op.drop_column('events', 'event_type')
