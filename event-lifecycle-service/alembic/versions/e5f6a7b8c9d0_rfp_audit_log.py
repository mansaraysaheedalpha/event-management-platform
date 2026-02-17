"""add rfp audit log table

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-02-17 16:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

# revision identifiers, used by Alembic.
revision = "e5f6a7b8c9d0"
down_revision = "d4e5f6a7b8c9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "rfp_audit_log",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("rfp_id", sa.String(), sa.ForeignKey("rfps.id", ondelete="CASCADE"), nullable=False),
        sa.Column("rfp_venue_id", sa.String(), sa.ForeignKey("rfp_venues.id", ondelete="SET NULL"), nullable=True),
        sa.Column("user_id", sa.String(), nullable=False),  # UUID from user service
        sa.Column("action", sa.String(50), nullable=False),  # 'award', 'decline', 'extend_deadline', etc.
        sa.Column("old_state", sa.String(50), nullable=True),
        sa.Column("new_state", sa.String(50), nullable=True),
        sa.Column("action_metadata", JSONB, nullable=True),  # {deadline_old: ..., deadline_new: ..., reason: ...}
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
    )

    # Indexes for efficient querying
    op.create_index("idx_audit_rfp_created", "rfp_audit_log", ["rfp_id", sa.text("created_at DESC")])
    op.create_index("idx_audit_user", "rfp_audit_log", ["user_id", sa.text("created_at DESC")])
    op.create_index("idx_audit_action", "rfp_audit_log", ["action"])


def downgrade() -> None:
    op.drop_index("idx_audit_action", "rfp_audit_log")
    op.drop_index("idx_audit_user", "rfp_audit_log")
    op.drop_index("idx_audit_rfp_created", "rfp_audit_log")
    op.drop_table("rfp_audit_log")
