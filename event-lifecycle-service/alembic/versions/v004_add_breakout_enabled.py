"""Add breakout_enabled to sessions

Revision ID: v004_add_breakout_enabled
Revises: v003_add_green_room_support
Create Date: 2026-01-17

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'v004_add_breakout_enabled'
down_revision: Union[str, None] = 'v003_add_green_room_support'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add breakout_enabled column with default false (opt-in feature)
    op.add_column(
        'sessions',
        sa.Column(
            'breakout_enabled',
            sa.Boolean(),
            nullable=False,
            server_default=sa.text('false'),
            comment='Enable breakout rooms for this session'
        )
    )


def downgrade() -> None:
    op.drop_column('sessions', 'breakout_enabled')
