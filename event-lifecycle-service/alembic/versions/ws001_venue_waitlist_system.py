"""venue waitlist system

Revision ID: ws001
Revises: vs001
Create Date: 2026-02-18 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers, used by Alembic.
revision = "ws001"
down_revision = "vs001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- Create venue_availability_signals table (append-only audit log) ---
    op.create_table(
        "venue_availability_signals",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("venue_id", sa.String(), nullable=False),
        sa.Column("signal_type", sa.String(), nullable=False),
        sa.Column("source_rfp_id", sa.String(), nullable=True),
        sa.Column("source_rfp_venue_id", sa.String(), nullable=True),
        sa.Column("signal_date", sa.Date(), nullable=True),
        sa.Column(
            "recorded_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("signal_metadata", JSONB, nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["venue_id"], ["venues.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["source_rfp_id"], ["rfps.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["source_rfp_venue_id"], ["rfp_venues.id"], ondelete="SET NULL"
        ),
    )

    # Indexes for venue_availability_signals
    op.create_index(
        "ix_vas_venue_recorded",
        "venue_availability_signals",
        ["venue_id", "recorded_at"],
    )
    op.create_index(
        "ix_vas_venue_signal_type",
        "venue_availability_signals",
        ["venue_id", "signal_type"],
    )
    op.create_index(
        "ix_venue_availability_signals_venue_id",
        "venue_availability_signals",
        ["venue_id"],
    )

    # --- Create venue_waitlist_entries table ---
    op.create_table(
        "venue_waitlist_entries",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("organization_id", sa.String(), nullable=False),
        sa.Column("venue_id", sa.String(), nullable=False),
        sa.Column("source_rfp_id", sa.String(), nullable=False),
        sa.Column("source_rfp_venue_id", sa.String(), nullable=False),
        # Context inherited from RFP
        sa.Column("desired_dates_start", sa.Date(), nullable=True),
        sa.Column("desired_dates_end", sa.Date(), nullable=True),
        sa.Column("dates_flexible", sa.Boolean(), nullable=False),
        sa.Column("attendance_min", sa.Integer(), nullable=False),
        sa.Column("attendance_max", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(), nullable=False),
        sa.Column(
            "space_requirements",
            JSONB,
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        # State
        sa.Column(
            "status", sa.String(), nullable=False, server_default=sa.text("'waiting'")
        ),
        # Hold tracking
        sa.Column("hold_offered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("hold_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "hold_reminder_sent",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        # Conversion
        sa.Column("converted_rfp_id", sa.String(), nullable=True),
        # Cancellation
        sa.Column("cancellation_reason", sa.String(), nullable=True),
        sa.Column("cancellation_notes", sa.Text(), nullable=True),
        # Expiry tracking
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("still_interested_sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "still_interested_responded",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        # Timestamps
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
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["venue_id"], ["venues.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["source_rfp_id"], ["rfps.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["source_rfp_venue_id"], ["rfp_venues.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["converted_rfp_id"], ["rfps.id"], ondelete="SET NULL"
        ),
    )

    # Indexes for venue_waitlist_entries
    op.create_index(
        "ix_vwl_org_status",
        "venue_waitlist_entries",
        ["organization_id", "status"],
    )
    op.create_index(
        "ix_vwl_venue_status", "venue_waitlist_entries", ["venue_id", "status"]
    )
    op.create_index(
        "ix_venue_waitlist_entries_organization_id",
        "venue_waitlist_entries",
        ["organization_id"],
    )
    op.create_index(
        "ix_venue_waitlist_entries_venue_id", "venue_waitlist_entries", ["venue_id"]
    )
    op.create_index(
        "ix_venue_waitlist_entries_source_rfp_id",
        "venue_waitlist_entries",
        ["source_rfp_id"],
    )

    # Partial indexes for background jobs
    op.execute(
        """
        CREATE INDEX ix_vwl_hold_expires
        ON venue_waitlist_entries(hold_expires_at)
        WHERE status = 'offered';
    """
    )
    op.execute(
        """
        CREATE INDEX ix_vwl_expires_at
        ON venue_waitlist_entries(expires_at)
        WHERE status = 'waiting';
    """
    )

    # Unique constraint: prevent duplicate active entries for same venue
    op.execute(
        """
        CREATE UNIQUE INDEX uq_vwl_org_venue_active
        ON venue_waitlist_entries(organization_id, venue_id)
        WHERE status IN ('waiting', 'offered');
    """
    )

    # --- Extend venues table with availability fields ---
    op.add_column(
        "venues",
        sa.Column(
            "availability_status",
            sa.String(),
            nullable=False,
            server_default=sa.text("'not_set'"),
        ),
    )
    op.add_column(
        "venues",
        sa.Column("availability_last_inferred_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "venues", sa.Column("availability_inferred_status", sa.String(), nullable=True)
    )
    op.add_column(
        "venues",
        sa.Column("availability_manual_override_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    # Drop venues columns
    op.drop_column("venues", "availability_manual_override_at")
    op.drop_column("venues", "availability_inferred_status")
    op.drop_column("venues", "availability_last_inferred_at")
    op.drop_column("venues", "availability_status")

    # Drop partial unique index
    op.execute("DROP INDEX IF EXISTS uq_vwl_org_venue_active")

    # Drop partial indexes
    op.execute("DROP INDEX IF EXISTS ix_vwl_expires_at")
    op.execute("DROP INDEX IF EXISTS ix_vwl_hold_expires")

    # Drop venue_waitlist_entries indexes
    op.drop_index("ix_venue_waitlist_entries_source_rfp_id", "venue_waitlist_entries")
    op.drop_index("ix_venue_waitlist_entries_venue_id", "venue_waitlist_entries")
    op.drop_index(
        "ix_venue_waitlist_entries_organization_id", "venue_waitlist_entries"
    )
    op.drop_index("ix_vwl_venue_status", "venue_waitlist_entries")
    op.drop_index("ix_vwl_org_status", "venue_waitlist_entries")

    # Drop venue_waitlist_entries table
    op.drop_table("venue_waitlist_entries")

    # Drop venue_availability_signals indexes
    op.drop_index(
        "ix_venue_availability_signals_venue_id", "venue_availability_signals"
    )
    op.drop_index("ix_vas_venue_signal_type", "venue_availability_signals")
    op.drop_index("ix_vas_venue_recorded", "venue_availability_signals")

    # Drop venue_availability_signals table
    op.drop_table("venue_availability_signals")
