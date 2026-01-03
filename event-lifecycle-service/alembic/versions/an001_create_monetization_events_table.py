"""Create monetization_events table for unified analytics

Revision ID: an001_create_monetization_events
Revises: a004_create_waitlist_tables
Create Date: 2025-12-31

This migration creates the monetization_events table for:
- Unified tracking across offers, ads, and waitlist
- Revenue attribution
- Conversion funnel analysis
- Comprehensive monetization analytics
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB, INET

# revision identifiers, used by Alembic.
revision = 'an001_monetization_events'
down_revision = 'a004_create_waitlist'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create monetization_events table
    op.execute("""
        CREATE TABLE monetization_events (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            event_id VARCHAR NOT NULL,
            user_id VARCHAR,
            session_token VARCHAR(255),

            -- Event Classification
            event_type VARCHAR(50) NOT NULL CHECK (event_type IN (
                -- Offer events
                'OFFER_VIEW', 'OFFER_CLICK', 'OFFER_ADD_TO_CART', 'OFFER_PURCHASE', 'OFFER_REFUND',
                -- Ad events
                'AD_IMPRESSION', 'AD_VIEWABLE_IMPRESSION', 'AD_CLICK',
                -- Waitlist events
                'WAITLIST_JOIN', 'WAITLIST_OFFER_SENT', 'WAITLIST_OFFER_ACCEPTED',
                'WAITLIST_OFFER_DECLINED', 'WAITLIST_OFFER_EXPIRED'
            )),
            entity_type VARCHAR(20) NOT NULL CHECK (entity_type IN ('OFFER', 'AD', 'WAITLIST')),
            entity_id VARCHAR NOT NULL,

            -- Revenue Attribution
            revenue_cents INT DEFAULT 0,
            currency VARCHAR(3) DEFAULT 'USD',

            -- Context
            context JSONB DEFAULT '{}'::jsonb,

            -- Technical
            user_agent TEXT,
            ip_address INET,

            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        );
    """)

    # Create indexes for performance
    op.execute("""
        CREATE INDEX idx_monetization_events_type
        ON monetization_events(event_type, created_at DESC);
    """)

    op.execute("""
        CREATE INDEX idx_monetization_events_entity
        ON monetization_events(entity_type, entity_id);
    """)

    op.execute("""
        CREATE INDEX idx_monetization_events_user
        ON monetization_events(user_id)
        WHERE user_id IS NOT NULL;
    """)

    op.execute("""
        CREATE INDEX idx_monetization_events_event
        ON monetization_events(event_id);
    """)

    op.execute("""
        CREATE INDEX idx_monetization_events_created
        ON monetization_events(created_at DESC);
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS monetization_events CASCADE;")
