"""Add Stripe Connect columns to organization_payment_settings and create organizer_payouts table

Revision ID: p003_connect_enhance
Revises: p004_fee_fields
Create Date: 2026-02-14

Phase 1: Stripe Connect Onboarding Backend.
Adds columns for Connect account status tracking (charges_enabled, payouts_enabled, etc.)
and creates the organizer_payouts table for logging payout events.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "p003_connect_enhance"
down_revision: Union[str, None] = "p004_fee_fields"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ---- ALTER organization_payment_settings ----
    # Add Stripe Connect status columns
    op.add_column(
        "organization_payment_settings",
        sa.Column("country", sa.String(2), server_default="US", nullable=True),
    )
    op.add_column(
        "organization_payment_settings",
        sa.Column(
            "charges_enabled",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
    )
    op.add_column(
        "organization_payment_settings",
        sa.Column(
            "payouts_enabled",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
    )
    op.add_column(
        "organization_payment_settings",
        sa.Column(
            "details_submitted",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
    )
    op.add_column(
        "organization_payment_settings",
        sa.Column(
            "requirements_json",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=True,
        ),
    )
    op.add_column(
        "organization_payment_settings",
        sa.Column(
            "fee_absorption",
            sa.String(20),
            server_default="absorb",
            nullable=False,
        ),
    )
    op.add_column(
        "organization_payment_settings",
        sa.Column("onboarding_completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "organization_payment_settings",
        sa.Column("deauthorized_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "organization_payment_settings",
        sa.Column("connected_email_sent_at", sa.DateTime(timezone=True), nullable=True),
    )

    # Add index on connected_account_id for webhook lookups
    op.create_index(
        "idx_org_payment_connected_account",
        "organization_payment_settings",
        ["connected_account_id"],
        postgresql_where=sa.text("connected_account_id IS NOT NULL"),
    )

    # ---- CREATE organizer_payouts table ----
    op.create_table(
        "organizer_payouts",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("organization_id", sa.String(), nullable=False),
        sa.Column("connected_account_id", sa.String(255), nullable=False),
        sa.Column("stripe_payout_id", sa.String(255), nullable=False),
        sa.Column("amount", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("status", sa.String(50), nullable=False),
        sa.Column("arrival_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failure_code", sa.String(100), nullable=True),
        sa.Column("failure_message", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_organizer_payouts_org",
        "organizer_payouts",
        ["organization_id"],
    )
    op.create_index(
        "idx_organizer_payouts_stripe_id",
        "organizer_payouts",
        ["stripe_payout_id"],
        unique=True,
    )
    op.create_index(
        "idx_organizer_payouts_account",
        "organizer_payouts",
        ["connected_account_id"],
    )

    # Add updated_at trigger for organizer_payouts
    op.execute("""
        CREATE OR REPLACE FUNCTION update_organizer_payouts_updated_at()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = now();
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)
    op.execute("""
        CREATE TRIGGER trg_organizer_payouts_updated_at
        BEFORE UPDATE ON organizer_payouts
        FOR EACH ROW
        EXECUTE FUNCTION update_organizer_payouts_updated_at();
    """)


def downgrade() -> None:
    # Drop trigger and function
    op.execute("DROP TRIGGER IF EXISTS trg_organizer_payouts_updated_at ON organizer_payouts;")
    op.execute("DROP FUNCTION IF EXISTS update_organizer_payouts_updated_at();")

    # Drop organizer_payouts table
    op.drop_index("idx_organizer_payouts_account", table_name="organizer_payouts")
    op.drop_index("idx_organizer_payouts_stripe_id", table_name="organizer_payouts")
    op.drop_index("idx_organizer_payouts_org", table_name="organizer_payouts")
    op.drop_table("organizer_payouts")

    # Drop index on connected_account_id
    op.drop_index(
        "idx_org_payment_connected_account",
        table_name="organization_payment_settings",
    )

    # Drop added columns
    op.drop_column("organization_payment_settings", "connected_email_sent_at")
    op.drop_column("organization_payment_settings", "deauthorized_at")
    op.drop_column("organization_payment_settings", "onboarding_completed_at")
    op.drop_column("organization_payment_settings", "fee_absorption")
    op.drop_column("organization_payment_settings", "requirements_json")
    op.drop_column("organization_payment_settings", "details_submitted")
    op.drop_column("organization_payment_settings", "payouts_enabled")
    op.drop_column("organization_payment_settings", "charges_enabled")
    op.drop_column("organization_payment_settings", "country")
