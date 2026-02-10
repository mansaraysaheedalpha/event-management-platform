"""add_registration_composite_indexes

Revision ID: r001_reg_indexes
Revises: e001_add_max_attendees
Create Date: 2026-02-10

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'r001_reg_indexes'
down_revision: Union[str, None] = 'e001_add_max_attendees'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Add composite indexes on registrations for the two hottest query patterns:
    1. (event_id, status, is_archived) — used by get_multi_by_event, get_count_by_event
    2. (user_id, is_archived, status)  — used by get_multi_by_user
    """
    op.create_index(
        'ix_registrations_event_status_archived',
        'registrations',
        ['event_id', 'status', 'is_archived'],
        unique=False,
    )
    op.create_index(
        'ix_registrations_user_archived_status',
        'registrations',
        ['user_id', 'is_archived', 'status'],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index('ix_registrations_user_archived_status', table_name='registrations')
    op.drop_index('ix_registrations_event_status_archived', table_name='registrations')
