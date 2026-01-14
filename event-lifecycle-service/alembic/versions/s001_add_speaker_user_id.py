"""Add user_id column to speakers table for backchannel role assignment

Revision ID: s001_add_speaker_user_id
Revises: v001_add_virtual_event_support
Create Date: 2026-01-14

This migration adds an optional user_id column to the speakers table,
allowing speakers to be linked to platform user accounts. This enables:
- Backchannel role-based targeting (whisper to speakers)
- Speaker-specific permissions and features
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "s001_add_speaker_user_id"
down_revision = "v001_add_virtual_event_support"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add user_id column to speakers table (nullable for backward compatibility)
    op.add_column(
        "speakers",
        sa.Column("user_id", sa.String(), nullable=True),
    )
    # Add index for efficient lookups by user_id
    op.create_index(
        "ix_speakers_user_id",
        "speakers",
        ["user_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_speakers_user_id", table_name="speakers")
    op.drop_column("speakers", "user_id")
