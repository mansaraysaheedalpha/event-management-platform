"""add_session_rsvp_user_schedule_index

Revision ID: 2f0384b1cf84
Revises: merge002_unify_feb_heads
Create Date: 2026-02-13 09:35:48.590267

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '2f0384b1cf84'
down_revision: Union[str, None] = 'merge002_unify_feb_heads'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Partial index for user schedule queries (only CONFIRMED RSVPs)
    # Optimizes: SELECT * FROM session_rsvps WHERE user_id = ? AND event_id = ? AND status = 'CONFIRMED'
    op.execute("""
        CREATE INDEX idx_session_rsvps_user_schedule
        ON session_rsvps(user_id, event_id)
        WHERE status = 'CONFIRMED'
    """)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_session_rsvps_user_schedule")
