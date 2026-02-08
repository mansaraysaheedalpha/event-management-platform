"""Add auto_captions and lobby_enabled to sessions

Revision ID: v006_add_auto_captions_lobby
Revises: v005_add_streaming_provider
Create Date: 2026-02-08

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "v006_add_auto_captions_lobby"
down_revision: Union[str, None] = "v005_add_streaming_provider"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "sessions",
        sa.Column(
            "auto_captions",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.add_column(
        "sessions",
        sa.Column(
            "lobby_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )


def downgrade() -> None:
    op.drop_column("sessions", "lobby_enabled")
    op.drop_column("sessions", "auto_captions")
