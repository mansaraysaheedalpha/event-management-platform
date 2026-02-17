"""rfp system models

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-02-16 22:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers, used by Alembic.
revision = "b2c3d4e5f6a7"
down_revision = "a1b2c3d4e5f6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- rfps ---
    op.create_table(
        "rfps",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("organization_id", sa.String(), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("event_type", sa.String(), nullable=False),
        sa.Column("attendance_min", sa.Integer(), nullable=False),
        sa.Column("attendance_max", sa.Integer(), nullable=False),
        sa.Column("preferred_dates_start", sa.Date(), nullable=True),
        sa.Column("preferred_dates_end", sa.Date(), nullable=True),
        sa.Column(
            "dates_flexible",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column("duration", sa.String(), nullable=False),
        sa.Column(
            "space_requirements",
            JSONB,
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "required_amenity_ids",
            JSONB,
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column("catering_needs", sa.String(), nullable=False),
        sa.Column("budget_min", sa.Numeric(14, 2), nullable=True),
        sa.Column("budget_max", sa.Numeric(14, 2), nullable=True),
        sa.Column("budget_currency", sa.String(3), nullable=True),
        sa.Column(
            "preferred_currency",
            sa.String(3),
            nullable=False,
            server_default=sa.text("'USD'"),
        ),
        sa.Column("additional_notes", sa.Text(), nullable=True),
        sa.Column(
            "response_deadline", sa.DateTime(timezone=True), nullable=False
        ),
        sa.Column("linked_event_id", sa.String(), nullable=True),
        sa.Column(
            "status",
            sa.String(),
            nullable=False,
            server_default=sa.text("'draft'"),
        ),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "is_template",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column("template_name", sa.String(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_rfps_organization_id", "rfps", ["organization_id"])
    op.create_index("ix_rfps_org_status", "rfps", ["organization_id", "status"])

    # --- rfp_venues ---
    op.create_table(
        "rfp_venues",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column(
            "rfp_id",
            sa.String(),
            sa.ForeignKey("rfps.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "venue_id",
            sa.String(),
            sa.ForeignKey("venues.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "status", sa.String(), nullable=False, server_default="received"
        ),
        sa.Column("notified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("viewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("responded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("capacity_fit", sa.String(), nullable=True),
        sa.Column("amenity_match_pct", sa.Float(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_rfp_venues_rfp_id", "rfp_venues", ["rfp_id"])
    op.create_index("ix_rfp_venues_venue_id", "rfp_venues", ["venue_id"])
    op.create_unique_constraint("uq_rfp_venue", "rfp_venues", ["rfp_id", "venue_id"])

    # --- venue_responses ---
    op.create_table(
        "venue_responses",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column(
            "rfp_venue_id",
            sa.String(),
            sa.ForeignKey("rfp_venues.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("availability", sa.String(), nullable=False),
        sa.Column("proposed_space_id", sa.String(), nullable=True),
        sa.Column("proposed_space_name", sa.String(), nullable=False),
        sa.Column("proposed_space_capacity", sa.Integer(), nullable=True),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("space_rental_price", sa.Numeric(14, 2), nullable=True),
        sa.Column("catering_price_per_head", sa.Numeric(14, 2), nullable=True),
        sa.Column("av_equipment_fees", sa.Numeric(14, 2), nullable=True),
        sa.Column("setup_cleanup_fees", sa.Numeric(14, 2), nullable=True),
        sa.Column("other_fees", sa.Numeric(14, 2), nullable=True),
        sa.Column("other_fees_description", sa.String(), nullable=True),
        sa.Column(
            "included_amenity_ids",
            JSONB,
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "extra_cost_amenities",
            JSONB,
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column("cancellation_policy", sa.Text(), nullable=True),
        sa.Column("deposit_amount", sa.Numeric(14, 2), nullable=True),
        sa.Column("payment_schedule", sa.Text(), nullable=True),
        sa.Column("alternative_dates", JSONB, nullable=True),
        sa.Column("quote_valid_until", sa.Date(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("total_estimated_cost", sa.Numeric(14, 2), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_venue_responses_rfp_venue_id", "venue_responses", ["rfp_venue_id"]
    )

    # --- negotiation_messages (schema only, no endpoints) ---
    op.create_table(
        "negotiation_messages",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column(
            "rfp_venue_id",
            sa.String(),
            sa.ForeignKey("rfp_venues.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("sender_type", sa.String(), nullable=False),
        sa.Column("message_type", sa.String(), nullable=False),
        sa.Column("content", JSONB, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_negotiation_messages_rfp_venue_id",
        "negotiation_messages",
        ["rfp_venue_id"],
    )


def downgrade() -> None:
    op.drop_table("negotiation_messages")
    op.drop_table("venue_responses")
    op.drop_table("rfp_venues")
    op.drop_table("rfps")
