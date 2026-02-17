"""add organizer email and deadline tracking to rfp system

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-02-17 14:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "c3d4e5f6a7b8"
down_revision = "b2c3d4e5f6a7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add organizer_email to rfps table for direct email notifications
    op.add_column(
        "rfps",
        sa.Column("organizer_email", sa.String(), nullable=True),
    )

    # Add deadline_processed_at to prevent duplicate deadline notifications
    op.add_column(
        "rfps",
        sa.Column("deadline_processed_at", sa.DateTime(timezone=True), nullable=True),
    )

    # Add deadline_reminder_sent_at to rfp_venues to prevent duplicate reminders
    op.add_column(
        "rfp_venues",
        sa.Column("deadline_reminder_sent_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("rfp_venues", "deadline_reminder_sent_at")
    op.drop_column("rfps", "deadline_processed_at")
    op.drop_column("rfps", "organizer_email")
