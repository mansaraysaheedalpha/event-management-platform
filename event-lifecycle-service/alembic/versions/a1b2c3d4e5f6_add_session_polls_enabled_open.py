"""add_session_polls_enabled_open

Revision ID: a1b2c3d4e5f6
Revises: f8a2c3d4e5b6
Create Date: 2025-12-15 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = 'f8a2c3d4e5b6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add polls_enabled column with default true (feature toggle)
    op.add_column(
        'sessions',
        sa.Column('polls_enabled', sa.Boolean(), nullable=False, server_default=sa.text('true'))
    )
    # Add polls_open column with default false (runtime state)
    op.add_column(
        'sessions',
        sa.Column('polls_open', sa.Boolean(), nullable=False, server_default=sa.text('false'))
    )


def downgrade() -> None:
    op.drop_column('sessions', 'polls_open')
    op.drop_column('sessions', 'polls_enabled')
