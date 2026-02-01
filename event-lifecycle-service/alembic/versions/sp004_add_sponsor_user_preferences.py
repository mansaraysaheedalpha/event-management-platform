"""add sponsor user profile and notification preferences

Revision ID: sp004
Revises: merge001_unify_heads
Create Date: 2026-01-30 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'sp004'
down_revision = 'merge001_unify_heads'
branch_labels = None
depends_on = None


def upgrade():
    # Add profile information columns
    op.add_column('sponsor_users', sa.Column('job_title', sa.String(length=100), nullable=True))
    op.add_column('sponsor_users', sa.Column('notification_email', sa.String(length=255), nullable=True))

    # Add notification preference columns with defaults
    op.add_column('sponsor_users', sa.Column('notify_new_leads', sa.Boolean(), nullable=False, server_default=sa.text('true')))
    op.add_column('sponsor_users', sa.Column('notify_hot_leads', sa.Boolean(), nullable=False, server_default=sa.text('true')))
    op.add_column('sponsor_users', sa.Column('notify_daily_summary', sa.Boolean(), nullable=False, server_default=sa.text('true')))
    op.add_column('sponsor_users', sa.Column('notify_event_updates', sa.Boolean(), nullable=False, server_default=sa.text('false')))
    op.add_column('sponsor_users', sa.Column('notify_marketing', sa.Boolean(), nullable=False, server_default=sa.text('false')))


def downgrade():
    # Remove notification preference columns
    op.drop_column('sponsor_users', 'notify_marketing')
    op.drop_column('sponsor_users', 'notify_event_updates')
    op.drop_column('sponsor_users', 'notify_daily_summary')
    op.drop_column('sponsor_users', 'notify_hot_leads')
    op.drop_column('sponsor_users', 'notify_new_leads')

    # Remove profile information columns
    op.drop_column('sponsor_users', 'notification_email')
    op.drop_column('sponsor_users', 'job_title')
