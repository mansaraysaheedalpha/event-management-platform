"""Merge February 2026 migration branches

Revision ID: merge002_unify_feb_heads
Revises: a007_create_session_rsvps, an005_monetization_indexes, r001_reg_indexes
Create Date: 2026-02-13

This merge migration consolidates three parallel branches from February 2026:
- a007_create_session_rsvps (session RSVP capacity tracking)
- an005_monetization_indexes (monetization query optimization)
- r001_reg_indexes (registration query optimization)
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'merge002_unify_feb_heads'
down_revision: Union[str, Sequence[str], None] = (
    'a007_create_session_rsvps',
    'an005_monetization_indexes',
    'r001_reg_indexes'
)
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Merge migration - no schema changes needed
    pass


def downgrade() -> None:
    # Merge migration - no schema changes needed
    pass
