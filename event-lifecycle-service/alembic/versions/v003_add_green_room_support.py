"""Add green room support to sessions

Revision ID: v003_add_green_room_support
Revises: v002_add_virtual_attendance
Create Date: 2026-01-17

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'v003_add_green_room_support'
down_revision: Union[str, None] = 'v002_add_virtual_attendance'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add green room fields to sessions table
    op.add_column('sessions', sa.Column(
        'green_room_enabled',
        sa.Boolean(),
        nullable=False,
        server_default=sa.text('true'),
        comment='Enable green room for speakers'
    ))
    op.add_column('sessions', sa.Column(
        'green_room_opens_minutes_before',
        sa.Integer(),
        nullable=False,
        server_default=sa.text('15'),
        comment='Minutes before session green room opens'
    ))
    op.add_column('sessions', sa.Column(
        'green_room_notes',
        sa.String(),
        nullable=True,
        comment='Producer notes visible in green room'
    ))


def downgrade() -> None:
    op.drop_column('sessions', 'green_room_notes')
    op.drop_column('sessions', 'green_room_opens_minutes_before')
    op.drop_column('sessions', 'green_room_enabled')
