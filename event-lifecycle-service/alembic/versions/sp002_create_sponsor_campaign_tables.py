"""Create sponsor campaign and delivery tracking tables

Revision ID: sp002_campaign_tables
Revises: sp001_sponsor_tables
Create Date: 2026-01-26

This migration creates tables for sponsor email campaigns:
- sponsor_campaigns: Tracks email campaigns sent by sponsors
- campaign_deliveries: Per-recipient delivery and engagement tracking

Production features:
- Audience filtering (hot, warm, all leads)
- Template variable substitution
- Async processing via Kafka
- Open/click tracking
- Delivery status per recipient
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSON

# revision identifiers, used by Alembic.
revision = 'sp002_campaign_tables'
down_revision = 'sp001_sponsor_tables'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ============================================
    # 1. Create sponsor_campaigns table
    # ============================================
    op.create_table(
        'sponsor_campaigns',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('sponsor_id', sa.String(), nullable=False),
        sa.Column('event_id', sa.String(), nullable=False),

        # Campaign Details
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('subject', sa.String(500), nullable=False),
        sa.Column('message_body', sa.Text(), nullable=False),

        # Audience Filtering
        sa.Column('audience_type', sa.String(20), nullable=False),
        sa.Column('audience_filter', JSON, nullable=True),

        # Sending Metadata
        sa.Column('total_recipients', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('sent_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('delivered_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('failed_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('opened_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('clicked_count', sa.Integer(), nullable=False, server_default='0'),

        # Status Tracking
        sa.Column('status', sa.String(20), nullable=False, server_default="'draft'"),

        # Scheduling
        sa.Column('scheduled_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),

        # Audit
        sa.Column('created_by_user_id', sa.String(), nullable=False),
        sa.Column('created_by_user_name', sa.String(200), nullable=True),

        # Error Tracking
        sa.Column('error_message', sa.Text(), nullable=True),

        # Metadata
        sa.Column('metadata', JSON, nullable=True, server_default='{}'),

        # Timestamps
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()')),

        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['sponsor_id'], ['sponsors.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['event_id'], ['events.id'], ondelete='CASCADE'),
    )

    # Indexes for sponsor_campaigns
    op.create_index('idx_sponsor_campaigns_sponsor', 'sponsor_campaigns', ['sponsor_id'])
    op.create_index('idx_sponsor_campaigns_event', 'sponsor_campaigns', ['event_id'])
    op.create_index('idx_sponsor_campaigns_status', 'sponsor_campaigns', ['status'])
    op.create_index('idx_sponsor_campaigns_created', 'sponsor_campaigns', ['created_at'])

    # ============================================
    # 2. Create campaign_deliveries table
    # ============================================
    op.create_table(
        'campaign_deliveries',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('campaign_id', sa.String(), nullable=False),
        sa.Column('lead_id', sa.String(), nullable=False),

        # Recipient Details (denormalized)
        sa.Column('recipient_email', sa.String(255), nullable=False),
        sa.Column('recipient_name', sa.String(200), nullable=True),

        # Personalized Content
        sa.Column('personalized_subject', sa.String(500), nullable=False),
        sa.Column('personalized_body', sa.Text(), nullable=False),

        # Delivery Status
        sa.Column('status', sa.String(20), nullable=False, server_default="'pending'"),

        # Email Service Provider Response
        sa.Column('provider_message_id', sa.String(500), nullable=True),
        sa.Column('provider_response', sa.Text(), nullable=True),

        # Engagement Tracking
        sa.Column('opened_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('opened_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('first_click_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('click_count', sa.Integer(), nullable=False, server_default='0'),

        # Error Tracking
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('retry_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('last_retry_at', sa.DateTime(timezone=True), nullable=True),

        # Timestamps
        sa.Column('queued_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('sent_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('delivered_at', sa.DateTime(timezone=True), nullable=True),

        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['campaign_id'], ['sponsor_campaigns.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['lead_id'], ['sponsor_leads.id'], ondelete='CASCADE'),
    )

    # Indexes for campaign_deliveries
    op.create_index('idx_campaign_deliveries_campaign', 'campaign_deliveries', ['campaign_id'])
    op.create_index('idx_campaign_deliveries_lead', 'campaign_deliveries', ['lead_id'])
    op.create_index('idx_campaign_deliveries_status', 'campaign_deliveries', ['status'])
    op.create_index('idx_campaign_deliveries_email', 'campaign_deliveries', ['recipient_email'])

    # Composite index for quick campaign analytics
    op.create_index(
        'idx_campaign_deliveries_campaign_status',
        'campaign_deliveries',
        ['campaign_id', 'status']
    )

    # Unique constraint to prevent duplicate sends to same lead
    op.create_index(
        'idx_campaign_deliveries_unique',
        'campaign_deliveries',
        ['campaign_id', 'lead_id'],
        unique=True
    )


def downgrade() -> None:
    # Drop tables in reverse order (due to foreign keys)
    op.drop_table('campaign_deliveries')
    op.drop_table('sponsor_campaigns')
