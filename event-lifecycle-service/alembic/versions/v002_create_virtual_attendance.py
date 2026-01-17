"""Create virtual attendance tracking table

Revision ID: v002_virtual_attendance
Revises: sp001_sponsor_tables
Create Date: 2026-01-16

This migration creates the virtual_attendance table for tracking
attendee participation in virtual sessions. This enables:
- Recording when attendees join/leave virtual sessions
- Tracking total watch time per attendee
- Analytics on virtual event engagement
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'v002_virtual_attendance'
down_revision = 'sp001_sponsor_tables'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ============================================
    # Create virtual_attendance table
    # ============================================
    op.create_table(
        'virtual_attendance',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('user_id', sa.String(), nullable=False, comment='User who attended'),
        sa.Column('session_id', sa.String(), nullable=False),
        sa.Column('event_id', sa.String(), nullable=False),
        sa.Column('joined_at', sa.DateTime(), nullable=False, server_default=sa.text('NOW()'),
                  comment='When the user joined the virtual session'),
        sa.Column('left_at', sa.DateTime(), nullable=True,
                  comment='When the user left (null if still watching)'),
        sa.Column('watch_duration_seconds', sa.Integer(), nullable=True,
                  comment='Total watch time in seconds (computed when user leaves)'),
        sa.Column('device_type', sa.String(), nullable=True,
                  comment='Device type: desktop, mobile, tablet'),
        sa.Column('user_agent', sa.String(), nullable=True,
                  comment='Browser/app user agent string'),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['session_id'], ['sessions.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['event_id'], ['events.id'], ondelete='CASCADE'),
    )

    # Create indexes for common queries
    op.create_index('ix_virtual_attendance_user_id', 'virtual_attendance', ['user_id'])
    op.create_index('ix_virtual_attendance_session_id', 'virtual_attendance', ['session_id'])
    op.create_index('ix_virtual_attendance_event_id', 'virtual_attendance', ['event_id'])
    op.create_index('ix_virtual_attendance_session_joined', 'virtual_attendance', ['session_id', 'joined_at'])
    op.create_index('ix_virtual_attendance_event_joined', 'virtual_attendance', ['event_id', 'joined_at'])
    op.create_index('ix_virtual_attendance_user_event', 'virtual_attendance', ['user_id', 'event_id'])


def downgrade() -> None:
    # Drop indexes first
    op.drop_index('ix_virtual_attendance_user_event', table_name='virtual_attendance')
    op.drop_index('ix_virtual_attendance_event_joined', table_name='virtual_attendance')
    op.drop_index('ix_virtual_attendance_session_joined', table_name='virtual_attendance')
    op.drop_index('ix_virtual_attendance_event_id', table_name='virtual_attendance')
    op.drop_index('ix_virtual_attendance_session_id', table_name='virtual_attendance')
    op.drop_index('ix_virtual_attendance_user_id', table_name='virtual_attendance')

    # Drop table
    op.drop_table('virtual_attendance')
