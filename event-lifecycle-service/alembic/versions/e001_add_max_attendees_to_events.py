"""Add max_attendees to events table

Revision ID: e001_add_max_attendees
Revises: d001_demo_requests
Create Date: 2026-02-10

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "e001_add_max_attendees"
down_revision: Union[str, None] = "d001_demo_requests"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "events",
        sa.Column("max_attendees", sa.Integer(), nullable=True),
    )
    op.create_check_constraint(
        "check_max_attendees_positive",
        "events",
        "max_attendees IS NULL OR max_attendees > 0",
    )


def downgrade() -> None:
    op.drop_constraint("check_max_attendees_positive", "events", type_="check")
    op.drop_column("events", "max_attendees")
