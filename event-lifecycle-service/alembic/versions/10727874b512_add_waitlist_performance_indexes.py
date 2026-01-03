"""add_waitlist_performance_indexes

Revision ID: 10727874b512
Revises: a004_create_waitlist
Create Date: 2025-12-31 15:38:52.082939

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '10727874b512'
down_revision: Union[str, None] = 'a004_create_waitlist'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Add performance indexes for waitlist queries.

    Indexes added:
    1. Composite index on (session_id, status) for common filtered queries
    2. Index on status column for status-based queries
    3. Composite index on (event_type, created_at) for event log queries (already exists)
    """
    # Add composite index on session_waitlist for common query pattern
    # WHERE session_id = ? AND status IN (...)
    op.create_index(
        'ix_session_waitlist_session_status',
        'session_waitlist',
        ['session_id', 'status'],
        unique=False
    )

    # Add standalone index on status for aggregate queries
    op.create_index(
        'ix_session_waitlist_status',
        'session_waitlist',
        ['status'],
        unique=False
    )


def downgrade() -> None:
    """Remove performance indexes"""
    op.drop_index('ix_session_waitlist_status', table_name='session_waitlist')
    op.drop_index('ix_session_waitlist_session_status', table_name='session_waitlist')
