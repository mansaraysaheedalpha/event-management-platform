"""add_session_chat_qa_open

Revision ID: f8a2c3d4e5b6
Revises: d561c55d9412
Create Date: 2025-12-11 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f8a2c3d4e5b6'
down_revision: Union[str, None] = 'd561c55d9412'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add chat_open column with default false
    op.add_column(
        'sessions',
        sa.Column('chat_open', sa.Boolean(), nullable=False, server_default=sa.text('false'))
    )
    # Add qa_open column with default false
    op.add_column(
        'sessions',
        sa.Column('qa_open', sa.Boolean(), nullable=False, server_default=sa.text('false'))
    )


def downgrade() -> None:
    op.drop_column('sessions', 'qa_open')
    op.drop_column('sessions', 'chat_open')
