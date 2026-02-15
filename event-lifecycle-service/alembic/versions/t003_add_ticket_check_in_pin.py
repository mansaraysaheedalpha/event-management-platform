"""Add check_in_pin column to tickets table

Revision ID: t003_ticket_check_in_pin
Revises: t002_ticket_expires_at
Create Date: 2026-02-15

Adds a 6-digit numeric PIN column to tickets for SMS/USSD-based check-in.
Attendees without smartphones can text their PIN to a shortcode to check in.
PINs are unique per event (not globally) to allow the same PIN to be reused
across different events.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "t003_ticket_check_in_pin"
down_revision: Union[str, None] = "t002_ticket_expires_at"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "tickets",
        sa.Column("check_in_pin", sa.String(6), nullable=True),
    )

    # Composite index for PIN lookup scoped to an event
    op.create_index(
        "idx_tickets_event_id_check_in_pin",
        "tickets",
        ["event_id", "check_in_pin"],
        unique=True,
        postgresql_where=sa.text("check_in_pin IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("idx_tickets_event_id_check_in_pin", table_name="tickets")
    op.drop_column("tickets", "check_in_pin")
