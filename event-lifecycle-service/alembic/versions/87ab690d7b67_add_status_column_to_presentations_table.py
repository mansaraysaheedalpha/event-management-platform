"""Add status column to presentations table

Revision ID: 87ab690d7b67
Revises: 97624f6f2e46
Create Date: 2025-10-09 14:13:49.804849

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '87ab690d7b67'
down_revision: Union[str, None] = '97624f6f2e46'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
