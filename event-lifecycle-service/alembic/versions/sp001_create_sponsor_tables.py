"""Create sponsor management tables

Revision ID: sp001_sponsor_tables
Revises: p002_pres_download_fields
Create Date: 2025-01-16

This migration creates all tables needed for sponsor management:
- sponsor_tiers: Sponsorship levels (Platinum, Gold, Silver, etc.)
- sponsors: Sponsor companies linked to events
- sponsor_users: Links users to sponsors they represent
- sponsor_invitations: Tracks pending invitations to sponsor reps
- sponsor_leads: Leads captured for sponsors
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSON

# revision identifiers, used by Alembic.
revision = 'sp001_sponsor_tables'
down_revision = 'p002_pres_download_fields'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ============================================
    # 1. Create sponsor_tiers table
    # ============================================
    op.create_table(
        'sponsor_tiers',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('organization_id', sa.String(), nullable=False),
        sa.Column('event_id', sa.String(), nullable=False),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('display_order', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('color', sa.String(7), nullable=True),
        sa.Column('benefits', JSON, nullable=False, server_default='[]'),
        sa.Column('booth_size', sa.String(20), nullable=True),
        sa.Column('logo_placement', sa.String(50), nullable=True),
        sa.Column('max_representatives', sa.Integer(), nullable=False, server_default='3'),
        sa.Column('can_capture_leads', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('can_export_leads', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('can_send_messages', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('price_cents', sa.Integer(), nullable=True),
        sa.Column('currency', sa.String(3), nullable=True, server_default='USD'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['event_id'], ['events.id'], ondelete='CASCADE'),
    )
    op.create_index('idx_sponsor_tiers_event', 'sponsor_tiers', ['event_id'])
    op.create_index('idx_sponsor_tiers_org', 'sponsor_tiers', ['organization_id'])

    # ============================================
    # 2. Create sponsors table
    # ============================================
    op.create_table(
        'sponsors',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('organization_id', sa.String(), nullable=False),
        sa.Column('event_id', sa.String(), nullable=False),
        sa.Column('tier_id', sa.String(), nullable=True),
        sa.Column('company_name', sa.String(200), nullable=False),
        sa.Column('company_description', sa.Text(), nullable=True),
        sa.Column('company_website', sa.String(500), nullable=True),
        sa.Column('company_logo_url', sa.String(500), nullable=True),
        sa.Column('contact_name', sa.String(200), nullable=True),
        sa.Column('contact_email', sa.String(255), nullable=True),
        sa.Column('contact_phone', sa.String(50), nullable=True),
        sa.Column('booth_number', sa.String(50), nullable=True),
        sa.Column('booth_description', sa.Text(), nullable=True),
        sa.Column('custom_booth_url', sa.String(500), nullable=True),
        sa.Column('social_links', JSON, nullable=True, server_default='{}'),
        sa.Column('marketing_assets', JSON, nullable=True, server_default='[]'),
        sa.Column('lead_capture_enabled', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('lead_notification_email', sa.String(255), nullable=True),
        sa.Column('custom_fields', JSON, nullable=True, server_default='{}'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('is_featured', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('is_archived', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['event_id'], ['events.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['tier_id'], ['sponsor_tiers.id'], ondelete='SET NULL'),
    )
    op.create_index('idx_sponsors_event', 'sponsors', ['event_id'])
    op.create_index('idx_sponsors_org', 'sponsors', ['organization_id'])
    op.create_index('idx_sponsors_tier', 'sponsors', ['tier_id'])
    op.create_index('idx_sponsors_active', 'sponsors', ['event_id'],
                    postgresql_where=sa.text('is_active = true AND is_archived = false'))

    # ============================================
    # 3. Create sponsor_users table
    # ============================================
    op.create_table(
        'sponsor_users',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('sponsor_id', sa.String(), nullable=False),
        sa.Column('user_id', sa.String(), nullable=False),
        sa.Column('role', sa.String(50), nullable=False, server_default='representative'),
        sa.Column('can_view_leads', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('can_export_leads', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('can_message_attendees', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('can_manage_booth', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('can_invite_others', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('joined_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('last_active_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['sponsor_id'], ['sponsors.id'], ondelete='CASCADE'),
        sa.UniqueConstraint('sponsor_id', 'user_id', name='uq_sponsor_user'),
    )
    op.create_index('idx_sponsor_users_sponsor', 'sponsor_users', ['sponsor_id'])
    op.create_index('idx_sponsor_users_user', 'sponsor_users', ['user_id'])

    # ============================================
    # 4. Create sponsor_invitations table
    # ============================================
    op.create_table(
        'sponsor_invitations',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('sponsor_id', sa.String(), nullable=False),
        sa.Column('email', sa.String(255), nullable=False),
        sa.Column('token', sa.String(64), nullable=False, unique=True),
        sa.Column('role', sa.String(50), nullable=False, server_default='representative'),
        sa.Column('can_view_leads', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('can_export_leads', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('can_message_attendees', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('can_manage_booth', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('can_invite_others', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('invited_by_user_id', sa.String(), nullable=False),
        sa.Column('personal_message', sa.String(500), nullable=True),
        sa.Column('status', sa.String(20), nullable=False, server_default='pending'),
        sa.Column('accepted_by_user_id', sa.String(), nullable=True),
        sa.Column('accepted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['sponsor_id'], ['sponsors.id'], ondelete='CASCADE'),
    )
    op.create_index('idx_sponsor_invitations_sponsor', 'sponsor_invitations', ['sponsor_id'])
    op.create_index('idx_sponsor_invitations_email', 'sponsor_invitations', ['email'])
    op.create_index('idx_sponsor_invitations_token', 'sponsor_invitations', ['token'], unique=True)
    op.create_index('idx_sponsor_invitations_pending', 'sponsor_invitations', ['sponsor_id'],
                    postgresql_where=sa.text("status = 'pending'"))

    # ============================================
    # 5. Create sponsor_leads table
    # ============================================
    op.create_table(
        'sponsor_leads',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('sponsor_id', sa.String(), nullable=False),
        sa.Column('event_id', sa.String(), nullable=False),
        sa.Column('user_id', sa.String(), nullable=False),
        sa.Column('user_name', sa.String(200), nullable=True),
        sa.Column('user_email', sa.String(255), nullable=True),
        sa.Column('user_company', sa.String(200), nullable=True),
        sa.Column('user_title', sa.String(200), nullable=True),
        sa.Column('intent_score', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('intent_level', sa.String(10), nullable=False, server_default='cold'),
        sa.Column('first_interaction_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('last_interaction_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('interaction_count', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('interactions', JSON, nullable=False, server_default='[]'),
        sa.Column('contact_requested', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('contact_notes', sa.Text(), nullable=True),
        sa.Column('preferred_contact_method', sa.String(20), nullable=True),
        sa.Column('follow_up_status', sa.String(20), nullable=False, server_default='new'),
        sa.Column('follow_up_notes', sa.Text(), nullable=True),
        sa.Column('followed_up_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('followed_up_by_user_id', sa.String(), nullable=True),
        sa.Column('tags', JSON, nullable=True, server_default='[]'),
        sa.Column('is_starred', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('is_archived', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['sponsor_id'], ['sponsors.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['event_id'], ['events.id'], ondelete='CASCADE'),
    )
    op.create_index('idx_sponsor_leads_sponsor', 'sponsor_leads', ['sponsor_id'])
    op.create_index('idx_sponsor_leads_event', 'sponsor_leads', ['event_id'])
    op.create_index('idx_sponsor_leads_user', 'sponsor_leads', ['user_id'])
    op.create_index('idx_sponsor_leads_intent', 'sponsor_leads', ['sponsor_id', 'intent_level'])
    op.create_index('idx_sponsor_leads_hot', 'sponsor_leads', ['sponsor_id'],
                    postgresql_where=sa.text("intent_level = 'hot' AND is_archived = false"))

    # Add check constraints
    op.create_check_constraint(
        'check_intent_level',
        'sponsor_leads',
        "intent_level IN ('hot', 'warm', 'cold')"
    )
    op.create_check_constraint(
        'check_follow_up_status',
        'sponsor_leads',
        "follow_up_status IN ('new', 'contacted', 'qualified', 'not_interested', 'converted')"
    )
    op.create_check_constraint(
        'check_invitation_status',
        'sponsor_invitations',
        "status IN ('pending', 'accepted', 'declined', 'expired', 'revoked')"
    )
    op.create_check_constraint(
        'check_sponsor_user_role',
        'sponsor_users',
        "role IN ('admin', 'representative', 'booth_staff', 'viewer')"
    )


def downgrade() -> None:
    # Drop check constraints
    op.drop_constraint('check_sponsor_user_role', 'sponsor_users', type_='check')
    op.drop_constraint('check_invitation_status', 'sponsor_invitations', type_='check')
    op.drop_constraint('check_follow_up_status', 'sponsor_leads', type_='check')
    op.drop_constraint('check_intent_level', 'sponsor_leads', type_='check')

    # Drop tables in reverse order (respecting foreign keys)
    op.drop_table('sponsor_leads')
    op.drop_table('sponsor_invitations')
    op.drop_table('sponsor_users')
    op.drop_table('sponsors')
    op.drop_table('sponsor_tiers')
