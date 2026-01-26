"""Merge virtual events and sponsor campaigns branches

Revision ID: merge_001_merge_heads
Revises: v004_add_breakout_enabled, sp002_campaign_tables
Create Date: 2026-01-26

This is a merge migration that combines the virtual events branch
and the sponsor campaigns branch into a single head.
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'merge_001_merge_heads'
down_revision: Union[str, Sequence[str], None] = ('v004_add_breakout_enabled', 'sp002_campaign_tables')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # This is a merge migration - no schema changes needed
    pass


def downgrade() -> None:
    # This is a merge migration - no schema changes needed
    pass
