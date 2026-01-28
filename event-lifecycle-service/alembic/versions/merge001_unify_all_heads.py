"""Merge all migration branches into single head

Revision ID: merge001_unify_heads
Revises: sp003_lead_stats_cache, merge_001_merge_heads
Create Date: 2026-01-28

This merge migration consolidates the two remaining parallel branches:
- sp003_lead_stats_cache (lead stats cache feature)
- merge_001_merge_heads (virtual events + sponsor campaigns merge)
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'merge001_unify_heads'
down_revision: Union[str, Sequence[str], None] = ('sp003_lead_stats_cache', 'merge_001_merge_heads')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Merge migration - no schema changes needed
    pass


def downgrade() -> None:
    # Merge migration - no schema changes needed
    pass
