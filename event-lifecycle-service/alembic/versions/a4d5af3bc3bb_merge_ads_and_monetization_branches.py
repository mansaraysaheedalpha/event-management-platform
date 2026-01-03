"""merge_ads_and_monetization_branches

Revision ID: a4d5af3bc3bb
Revises: a003_create_ad_analytics, m003_performance_indexes
Create Date: 2025-12-30 23:16:42.821972

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a4d5af3bc3bb'
down_revision: Union[str, None] = ('a003_create_ad_analytics', 'm003_performance_indexes')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
