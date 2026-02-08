"""Add streaming_provider to sessions

Revision ID: v005_add_streaming_provider
Revises: v004_add_breakout_enabled
Create Date: 2026-02-08

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "v005_add_streaming_provider"
down_revision: Union[str, None] = "v004_add_breakout_enabled"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "sessions",
        sa.Column("streaming_provider", sa.String(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("sessions", "streaming_provider")
