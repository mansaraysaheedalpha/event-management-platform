"""Add reactions_enabled and reactions_open to sessions

Revision ID: v007_add_reactions
Revises: v006_add_auto_captions_lobby
Create Date: 2026-02-08

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "v007_add_reactions"
down_revision: Union[str, None] = "v006_add_auto_captions_lobby"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "sessions",
        sa.Column(
            "reactions_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
    )
    op.add_column(
        "sessions",
        sa.Column(
            "reactions_open",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )


def downgrade() -> None:
    op.drop_column("sessions", "reactions_open")
    op.drop_column("sessions", "reactions_enabled")
