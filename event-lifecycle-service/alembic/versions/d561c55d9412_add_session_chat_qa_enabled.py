"""add_session_chat_qa_enabled

Revision ID: d561c55d9412
Revises: 87ab690d7b67
Create Date: 2025-12-11 04:18:06.997889

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd561c55d9412'
down_revision: Union[str, None] = '87ab690d7b67'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
