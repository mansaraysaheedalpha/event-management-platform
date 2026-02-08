"""Create demo_requests table

Revision ID: d001_demo_requests
Revises: v007_add_reactions
Create Date: 2026-02-08

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "d001_demo_requests"
down_revision: Union[str, None] = "v007_add_reactions"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "demo_requests",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("first_name", sa.String(), nullable=False),
        sa.Column("last_name", sa.String(), nullable=False),
        sa.Column("email", sa.String(), nullable=False),
        sa.Column("company", sa.String(), nullable=False),
        sa.Column("job_title", sa.String(), nullable=True),
        sa.Column("company_size", sa.String(), nullable=False),
        sa.Column("solution_interest", sa.String(), nullable=True),
        sa.Column("preferred_date", sa.String(), nullable=True),
        sa.Column("preferred_time", sa.String(), nullable=True),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column(
            "status",
            sa.String(),
            nullable=False,
            server_default=sa.text("'pending'"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_demo_requests_email"), "demo_requests", ["email"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_demo_requests_email"), table_name="demo_requests")
    op.drop_table("demo_requests")
