"""Enhance ads table with full advertisement features

Revision ID: a001_enhance_ads
Revises: t001_ticket_mgmt
Create Date: 2025-12-30

This migration enhances the ads table with:
- Display settings (duration, aspect ratio)
- Scheduling fields (starts_at, ends_at)
- Targeting fields (placements, target_sessions)
- Rotation and frequency control (weight, frequency_cap)
- Status and metadata fields
- Proper constraints and indexes
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ARRAY

# revision identifiers, used by Alembic.
revision = 'a001_enhance_ads'
down_revision = 't001_ticket_mgmt'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add display settings
    op.add_column('ads', sa.Column('display_duration_seconds', sa.Integer(), nullable=False, server_default='30'))
    op.add_column('ads', sa.Column('aspect_ratio', sa.String(20), nullable=False, server_default='16:9'))

    # Add scheduling
    op.add_column('ads', sa.Column('starts_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()')))
    op.add_column('ads', sa.Column('ends_at', sa.DateTime(timezone=True), nullable=True))

    # Add targeting (placements as array, target_sessions as array)
    op.add_column('ads', sa.Column('placements', ARRAY(sa.String(50)), nullable=False, server_default="{'EVENT_HERO'}"))
    op.add_column('ads', sa.Column('target_sessions', ARRAY(sa.String()), nullable=True, server_default='{}'))

    # Add rotation and frequency control
    op.add_column('ads', sa.Column('weight', sa.Integer(), nullable=False, server_default='1'))
    op.add_column('ads', sa.Column('frequency_cap', sa.Integer(), nullable=False, server_default='3'))

    # Add status
    op.add_column('ads', sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'))

    # Add metadata
    op.add_column('ads', sa.Column('metadata', sa.JSON(), nullable=True, server_default='{}'))

    # Add timestamps
    op.add_column('ads', sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()')))
    op.add_column('ads', sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()')))

    # Add constraints
    op.create_check_constraint(
        'check_content_type',
        'ads',
        "content_type IN ('BANNER', 'VIDEO', 'SPONSORED_SESSION', 'INTERSTITIAL')"
    )

    op.create_check_constraint(
        'check_display_duration_positive',
        'ads',
        'display_duration_seconds > 0'
    )

    op.create_check_constraint(
        'check_weight_positive',
        'ads',
        'weight > 0'
    )

    # Add indexes for performance
    op.create_index('idx_ads_event_active', 'ads', ['event_id'],
                    postgresql_where=sa.text('is_active = true AND is_archived = false'))
    op.create_index('idx_ads_schedule', 'ads', ['starts_at', 'ends_at'],
                    postgresql_where=sa.text('is_active = true'))
    op.create_index('idx_ads_organization', 'ads', ['organization_id'],
                    postgresql_where=sa.text('is_archived = false'))


def downgrade() -> None:
    # Drop indexes
    op.drop_index('idx_ads_organization', table_name='ads')
    op.drop_index('idx_ads_schedule', table_name='ads')
    op.drop_index('idx_ads_event_active', table_name='ads')

    # Drop constraints
    op.drop_constraint('check_weight_positive', 'ads', type_='check')
    op.drop_constraint('check_display_duration_positive', 'ads', type_='check')
    op.drop_constraint('check_content_type', 'ads', type_='check')

    # Drop columns
    op.drop_column('ads', 'updated_at')
    op.drop_column('ads', 'created_at')
    op.drop_column('ads', 'metadata')
    op.drop_column('ads', 'is_active')
    op.drop_column('ads', 'frequency_cap')
    op.drop_column('ads', 'weight')
    op.drop_column('ads', 'target_sessions')
    op.drop_column('ads', 'placements')
    op.drop_column('ads', 'ends_at')
    op.drop_column('ads', 'starts_at')
    op.drop_column('ads', 'aspect_ratio')
    op.drop_column('ads', 'display_duration_seconds')
