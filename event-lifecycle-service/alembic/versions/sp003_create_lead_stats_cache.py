"""Create lead stats cache table and trigger

Revision ID: sp003_lead_stats_cache
Revises: sp002_campaign_tables
Create Date: 2026-01-28

This migration creates infrastructure for real-time lead statistics:
- sponsor_lead_stats_cache: Pre-computed statistics per sponsor
- PostgreSQL trigger to auto-update stats on lead changes
- Materialized view for complex analytics queries

Benefits:
- Eliminates N+1 queries for stats aggregation
- Sub-millisecond stats retrieval from cache
- Real-time updates via trigger
- Consistent stats across all dashboard views
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSON

# revision identifiers, used by Alembic.
revision = 'sp003_lead_stats_cache'
# Merge migration: combines sp002_campaign_tables and v002_virtual_attendance branches
down_revision = ('sp002_campaign_tables', 'v002_virtual_attendance')
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ============================================
    # 1. Create sponsor_lead_stats_cache table
    # ============================================
    op.create_table(
        'sponsor_lead_stats_cache',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('sponsor_id', sa.String(), nullable=False),
        sa.Column('event_id', sa.String(), nullable=False),

        # Lead counts by intent level
        sa.Column('total_leads', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('hot_leads', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('warm_leads', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('cold_leads', sa.Integer(), nullable=False, server_default='0'),

        # Follow-up tracking
        sa.Column('leads_contacted', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('leads_converted', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('conversion_rate', sa.Numeric(5, 2), nullable=False, server_default='0'),

        # Scoring metrics
        sa.Column('avg_intent_score', sa.Numeric(5, 1), nullable=False, server_default='0'),
        sa.Column('max_intent_score', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('min_intent_score', sa.Integer(), nullable=False, server_default='0'),

        # Engagement metrics
        sa.Column('total_interactions', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('avg_interactions_per_lead', sa.Numeric(5, 2), nullable=False, server_default='0'),

        # Timestamps
        sa.Column('last_lead_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('calculated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()')),

        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['sponsor_id'], ['sponsors.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['event_id'], ['events.id'], ondelete='CASCADE'),
        sa.UniqueConstraint('sponsor_id', 'event_id', name='uq_lead_stats_sponsor_event'),
    )

    # Indexes for fast lookups
    op.create_index('idx_lead_stats_sponsor', 'sponsor_lead_stats_cache', ['sponsor_id'])
    op.create_index('idx_lead_stats_event', 'sponsor_lead_stats_cache', ['event_id'])
    op.create_index('idx_lead_stats_calculated', 'sponsor_lead_stats_cache', ['calculated_at'])

    # ============================================
    # 2. Create function to update lead stats
    # ============================================
    op.execute("""
        CREATE OR REPLACE FUNCTION update_sponsor_lead_stats()
        RETURNS TRIGGER AS $$
        DECLARE
            v_sponsor_id VARCHAR;
            v_event_id VARCHAR;
            v_stats RECORD;
        BEGIN
            -- Determine which sponsor/event to update
            IF TG_OP = 'DELETE' THEN
                v_sponsor_id := OLD.sponsor_id;
                v_event_id := OLD.event_id;
            ELSE
                v_sponsor_id := NEW.sponsor_id;
                v_event_id := NEW.event_id;
            END IF;

            -- Calculate fresh stats for this sponsor
            SELECT
                COUNT(*) as total_leads,
                COUNT(*) FILTER (WHERE intent_level = 'hot' AND is_archived = false) as hot_leads,
                COUNT(*) FILTER (WHERE intent_level = 'warm' AND is_archived = false) as warm_leads,
                COUNT(*) FILTER (WHERE intent_level = 'cold' AND is_archived = false) as cold_leads,
                COUNT(*) FILTER (WHERE follow_up_status != 'new' AND is_archived = false) as leads_contacted,
                COUNT(*) FILTER (WHERE follow_up_status = 'converted' AND is_archived = false) as leads_converted,
                COALESCE(AVG(intent_score) FILTER (WHERE is_archived = false), 0) as avg_intent_score,
                COALESCE(MAX(intent_score) FILTER (WHERE is_archived = false), 0) as max_intent_score,
                COALESCE(MIN(intent_score) FILTER (WHERE is_archived = false), 0) as min_intent_score,
                COALESCE(SUM(interaction_count) FILTER (WHERE is_archived = false), 0) as total_interactions,
                MAX(created_at) FILTER (WHERE is_archived = false) as last_lead_at
            INTO v_stats
            FROM sponsor_leads
            WHERE sponsor_id = v_sponsor_id AND is_archived = false;

            -- Upsert the stats cache
            INSERT INTO sponsor_lead_stats_cache (
                id, sponsor_id, event_id,
                total_leads, hot_leads, warm_leads, cold_leads,
                leads_contacted, leads_converted, conversion_rate,
                avg_intent_score, max_intent_score, min_intent_score,
                total_interactions, avg_interactions_per_lead,
                last_lead_at, calculated_at, updated_at
            ) VALUES (
                'slsc_' || substring(md5(random()::text), 1, 12),
                v_sponsor_id, v_event_id,
                COALESCE(v_stats.total_leads, 0),
                COALESCE(v_stats.hot_leads, 0),
                COALESCE(v_stats.warm_leads, 0),
                COALESCE(v_stats.cold_leads, 0),
                COALESCE(v_stats.leads_contacted, 0),
                COALESCE(v_stats.leads_converted, 0),
                CASE WHEN v_stats.total_leads > 0
                    THEN ROUND((v_stats.leads_converted::numeric / v_stats.total_leads) * 100, 2)
                    ELSE 0
                END,
                ROUND(v_stats.avg_intent_score::numeric, 1),
                COALESCE(v_stats.max_intent_score, 0),
                COALESCE(v_stats.min_intent_score, 0),
                COALESCE(v_stats.total_interactions, 0),
                CASE WHEN v_stats.total_leads > 0
                    THEN ROUND((v_stats.total_interactions::numeric / v_stats.total_leads), 2)
                    ELSE 0
                END,
                v_stats.last_lead_at,
                NOW(),
                NOW()
            )
            ON CONFLICT (sponsor_id, event_id) DO UPDATE SET
                total_leads = EXCLUDED.total_leads,
                hot_leads = EXCLUDED.hot_leads,
                warm_leads = EXCLUDED.warm_leads,
                cold_leads = EXCLUDED.cold_leads,
                leads_contacted = EXCLUDED.leads_contacted,
                leads_converted = EXCLUDED.leads_converted,
                conversion_rate = EXCLUDED.conversion_rate,
                avg_intent_score = EXCLUDED.avg_intent_score,
                max_intent_score = EXCLUDED.max_intent_score,
                min_intent_score = EXCLUDED.min_intent_score,
                total_interactions = EXCLUDED.total_interactions,
                avg_interactions_per_lead = EXCLUDED.avg_interactions_per_lead,
                last_lead_at = EXCLUDED.last_lead_at,
                calculated_at = EXCLUDED.calculated_at,
                updated_at = NOW();

            RETURN NULL; -- Trigger function return value is ignored for AFTER triggers
        END;
        $$ LANGUAGE plpgsql;
    """)

    # ============================================
    # 3. Create trigger on sponsor_leads table
    # ============================================
    op.execute("""
        CREATE TRIGGER trigger_update_lead_stats
        AFTER INSERT OR UPDATE OR DELETE ON sponsor_leads
        FOR EACH ROW EXECUTE FUNCTION update_sponsor_lead_stats();
    """)

    # ============================================
    # 4. Create materialized view for analytics
    # ============================================
    op.execute("""
        CREATE MATERIALIZED VIEW sponsor_lead_analytics AS
        SELECT
            sponsor_id,
            event_id,
            COUNT(*) as total_leads,
            COUNT(*) FILTER (WHERE intent_level = 'hot') as hot_leads,
            COUNT(*) FILTER (WHERE intent_level = 'warm') as warm_leads,
            COUNT(*) FILTER (WHERE intent_level = 'cold') as cold_leads,
            COUNT(*) FILTER (WHERE follow_up_status != 'new') as leads_contacted,
            COUNT(*) FILTER (WHERE follow_up_status = 'converted') as leads_converted,
            ROUND(AVG(intent_score)::numeric, 1) as avg_intent_score,
            DATE(created_at) as lead_date,
            COUNT(*) as leads_that_day
        FROM sponsor_leads
        WHERE is_archived = false
        GROUP BY sponsor_id, event_id, DATE(created_at);
    """)

    # Unique index for concurrent refresh
    op.execute("""
        CREATE UNIQUE INDEX idx_sponsor_lead_analytics_unique
        ON sponsor_lead_analytics (sponsor_id, event_id, lead_date);
    """)

    # Index for sponsor lookups
    op.execute("""
        CREATE INDEX idx_sponsor_lead_analytics_sponsor
        ON sponsor_lead_analytics (sponsor_id);
    """)


def downgrade() -> None:
    # Drop materialized view
    op.execute("DROP MATERIALIZED VIEW IF EXISTS sponsor_lead_analytics;")

    # Drop trigger
    op.execute("DROP TRIGGER IF EXISTS trigger_update_lead_stats ON sponsor_leads;")

    # Drop function
    op.execute("DROP FUNCTION IF EXISTS update_sponsor_lead_stats();")

    # Drop indexes
    op.drop_index('idx_lead_stats_calculated', 'sponsor_lead_stats_cache')
    op.drop_index('idx_lead_stats_event', 'sponsor_lead_stats_cache')
    op.drop_index('idx_lead_stats_sponsor', 'sponsor_lead_stats_cache')

    # Drop table
    op.drop_table('sponsor_lead_stats_cache')
