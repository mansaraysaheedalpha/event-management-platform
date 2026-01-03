"""merge_ab_testing_and_waitlist

Revision ID: 4a57803bead0
Revises: 10727874b512, abt001_ab_testing_tables
Create Date: 2026-01-01 04:16:33.205777

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4a57803bead0'
down_revision: Union[str, None] = ('10727874b512', 'abt001_ab_testing_tables')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
