"""Merge all migration branches into single head

Revision ID: merge001_unify_heads
Revises: sp003_lead_stats_cache, abt001_ab_testing_tables, a003_create_ad_analytics, m003_performance_indexes
Create Date: 2026-01-28

This merge migration consolidates all parallel branches into a single head.
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'merge001_unify_heads'
down_revision = ('sp003_lead_stats_cache', 'abt001_ab_testing_tables', 'a003_create_ad_analytics', 'm003_performance_indexes')
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Merge migration - no schema changes needed
    pass


def downgrade() -> None:
    # Merge migration - no schema changes needed
    pass
