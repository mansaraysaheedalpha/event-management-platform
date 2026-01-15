"""Add download feature fields to presentations table

Revision ID: p002_pres_download_fields
Revises: s001_add_speaker_user_id
Create Date: 2026-01-14

This migration adds columns to support the presentation download feature:
- download_enabled: Boolean to toggle download availability for attendees
- original_file_key: S3 key of the original uploaded file
- original_filename: Original filename for display and download
- created_at: Timestamp when the presentation was created
- updated_at: Timestamp when the presentation was last updated
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "p002_pres_download_fields"
down_revision = "s001_add_speaker_user_id"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add download_enabled column (defaults to False)
    op.add_column(
        "presentations",
        sa.Column(
            "download_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )

    # Add original_file_key column for S3 storage reference
    op.add_column(
        "presentations",
        sa.Column("original_file_key", sa.String(), nullable=True),
    )

    # Add original_filename column for user-friendly download names
    op.add_column(
        "presentations",
        sa.Column("original_filename", sa.String(), nullable=True),
    )

    # Add created_at timestamp
    op.add_column(
        "presentations",
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    # Add updated_at timestamp
    op.add_column(
        "presentations",
        sa.Column(
            "updated_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    # Add index on download_enabled for efficient queries
    op.create_index(
        "ix_presentations_download_enabled",
        "presentations",
        ["download_enabled"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_presentations_download_enabled", table_name="presentations")
    op.drop_column("presentations", "updated_at")
    op.drop_column("presentations", "created_at")
    op.drop_column("presentations", "original_filename")
    op.drop_column("presentations", "original_file_key")
    op.drop_column("presentations", "download_enabled")
