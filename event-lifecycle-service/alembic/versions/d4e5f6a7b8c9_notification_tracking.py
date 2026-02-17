"""add notification tracking table

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-02-17 15:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

# revision identifiers, used by Alembic.
revision = "d4e5f6a7b8c9"
down_revision = "c3d4e5f6a7b8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "rfp_notifications",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("rfp_id", sa.String(), sa.ForeignKey("rfps.id", ondelete="CASCADE"), nullable=False),
        sa.Column("rfp_venue_id", sa.String(), sa.ForeignKey("rfp_venues.id", ondelete="CASCADE"), nullable=True),
        sa.Column("recipient_type", sa.String(20), nullable=False),  # 'venue_owner' or 'organizer'
        sa.Column("recipient_id", sa.String(), nullable=False),  # user_id or organization_id
        sa.Column("recipient_identifier", sa.String(255), nullable=True),  # email address or phone number
        sa.Column("channel", sa.String(20), nullable=False),  # 'email', 'whatsapp', 'inapp'
        sa.Column("event_type", sa.String(50), nullable=False),  # 'rfp.new_request', 'deadline_passed', etc.
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),  # 'pending', 'sent', 'delivered', 'failed'
        sa.Column("external_id", sa.String(255), nullable=True),  # Resend message ID, AT message ID
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
    )

    # Indexes for efficient querying
    op.create_index("idx_rfp_notif_rfp", "rfp_notifications", ["rfp_id"])
    op.create_index("idx_rfp_notif_recipient", "rfp_notifications", ["recipient_id", "channel"])
    op.create_index("idx_rfp_notif_status", "rfp_notifications", ["status", "created_at"])
    op.create_index("idx_rfp_notif_event", "rfp_notifications", ["event_type"])


def downgrade() -> None:
    op.drop_index("idx_rfp_notif_event", "rfp_notifications")
    op.drop_index("idx_rfp_notif_status", "rfp_notifications")
    op.drop_index("idx_rfp_notif_recipient", "rfp_notifications")
    op.drop_index("idx_rfp_notif_rfp", "rfp_notifications")
    op.drop_table("rfp_notifications")
