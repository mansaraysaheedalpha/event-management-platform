"""Create session_capacity table

Revision ID: a005_create_session_capacity
Revises: 4a57803bead0
Create Date: 2026-01-03

This migration creates the session_capacity table for managing
session attendance capacity dynamically.
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'a005_create_session_capacity'
down_revision = '4a57803bead0'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create session_capacity table
    op.create_table(
        'session_capacity',
        sa.Column('session_id', sa.String(), sa.ForeignKey('sessions.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('maximum_capacity', sa.Integer(), nullable=False, server_default='100'),
        sa.Column('current_attendance', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()'), onupdate=sa.text('NOW()'))
    )

    # Add check constraints
    op.create_check_constraint(
        'check_capacity_positive',
        'session_capacity',
        'maximum_capacity >= 0'
    )

    op.create_check_constraint(
        'check_attendance_positive',
        'session_capacity',
        'current_attendance >= 0'
    )

    op.create_check_constraint(
        'check_attendance_lte_capacity',
        'session_capacity',
        'current_attendance <= maximum_capacity'
    )

    # Create index for quick lookups
    op.create_index('idx_session_capacity_session', 'session_capacity', ['session_id'])


def downgrade() -> None:
    # Drop session_capacity table and its indexes
    op.drop_index('idx_session_capacity_session', table_name='session_capacity')
    op.drop_constraint('check_attendance_lte_capacity', 'session_capacity', type_='check')
    op.drop_constraint('check_attendance_positive', 'session_capacity', type_='check')
    op.drop_constraint('check_capacity_positive', 'session_capacity', type_='check')
    op.drop_table('session_capacity')
