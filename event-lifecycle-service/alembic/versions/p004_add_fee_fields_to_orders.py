"""Add Stripe Connect fee fields to orders table

Revision ID: p004_fee_fields
Revises: merge002_unify_feb_heads
Create Date: 2026-02-14

Phase 2: Wire up platform fees and destination charges.
Adds columns to track fee breakdown, absorption model, and connected account
per order for Stripe Connect marketplace payments.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "p004_fee_fields"
down_revision: Union[str, None] = "merge002_unify_feb_heads"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add Stripe Connect fee fields to orders table
    op.add_column(
        "orders",
        sa.Column("subtotal_amount", sa.Integer(), nullable=True),
    )
    op.add_column(
        "orders",
        sa.Column(
            "fee_absorption",
            sa.String(20),
            server_default="absorb",
            nullable=True,
        ),
    )
    op.add_column(
        "orders",
        sa.Column(
            "fee_breakdown_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
    )
    op.add_column(
        "orders",
        sa.Column("connected_account_id", sa.String(255), nullable=True),
    )

    # Backfill: set subtotal_amount = total_amount for existing orders
    # so existing orders have consistent data
    op.execute(
        "UPDATE orders SET subtotal_amount = total_amount WHERE subtotal_amount IS NULL"
    )


def downgrade() -> None:
    op.drop_column("orders", "connected_account_id")
    op.drop_column("orders", "fee_breakdown_json")
    op.drop_column("orders", "fee_absorption")
    op.drop_column("orders", "subtotal_amount")
