"""Add expires_at column to tickets table

Revision ID: t002_ticket_expires_at
Revises: p005_revenue_views
Create Date: 2026-02-15

Adds an expires_at column (DateTime with timezone, nullable) to the tickets
table. This column supports future expiration enforcement for ticket QR codes,
allowing time-based invalidation independent of the JWT exp claim.

Used in conjunction with the JWT-signed QR codes (v2 format) to enforce
server-side expiration even if the JWT has not yet expired.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "t002_ticket_expires_at"
down_revision: Union[str, None] = "p005_revenue_views"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "tickets",
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
    )

    # Index for efficient queries on expiring/expired tickets
    op.create_index(
        "idx_tickets_expires_at",
        "tickets",
        ["expires_at"],
        postgresql_where=sa.text("expires_at IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("idx_tickets_expires_at", table_name="tickets")
    op.drop_column("tickets", "expires_at")
