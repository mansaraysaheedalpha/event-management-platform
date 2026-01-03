"""Add table partitioning to monetization_events (OPTIONAL)

Revision ID: an003_add_events_partitioning
Revises: an002_create_monetization_funnels
Create Date: 2025-12-31

⚠️ WARNING: This migration adds table partitioning for better scalability.
⚠️ It requires RECREATING the table, which will DELETE all existing data.
⚠️ Only run this BEFORE production data exists OR with a proper migration strategy.

Benefits:
- 50-80% faster queries on large datasets
- Easier data archival
- Better index performance

When to Apply:
- Before production launch (recommended)
- OR when table exceeds 10 million rows
- OR if experiencing query slowdowns

How to Apply:
1. Export existing data: pg_dump -t monetization_events
2. Run migration: alembic upgrade an003_add_events_partitioning
3. Re-import data if needed

IMPORTANT: This migration is OPTIONAL and can be skipped if:
- You're in early development
- Table is still small (<1M rows)
- You prefer to apply it later
"""

from alembic import op

# revision identifiers, used by Alembic.
revision = 'an003_events_partitioning'
down_revision = 'an002_monetization_funnels'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    CAUTION: This will recreate the table. Backup data first!
    """

    # Drop the existing table (⚠️ DATA LOSS WARNING)
    op.execute("DROP TABLE IF EXISTS monetization_events CASCADE;")

    # Create partitioned table
    op.execute("""
        CREATE TABLE monetization_events (
            id UUID DEFAULT gen_random_uuid(),
            event_id VARCHAR NOT NULL,
            user_id VARCHAR,
            session_token VARCHAR(255),

            -- Event Classification
            event_type VARCHAR(50) NOT NULL CHECK (event_type IN (
                'OFFER_VIEW', 'OFFER_CLICK', 'OFFER_ADD_TO_CART', 'OFFER_PURCHASE', 'OFFER_REFUND',
                'AD_IMPRESSION', 'AD_VIEWABLE_IMPRESSION', 'AD_CLICK',
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

            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,

            PRIMARY KEY (id, created_at)
        ) PARTITION BY RANGE (created_at);
    """)

    # Create initial partitions (last 3 months + future)
    # Adjust dates based on your needs
    op.execute("""
        CREATE TABLE monetization_events_2025_01 PARTITION OF monetization_events
            FOR VALUES FROM ('2025-01-01') TO ('2025-02-01');
    """)

    op.execute("""
        CREATE TABLE monetization_events_2025_02 PARTITION OF monetization_events
            FOR VALUES FROM ('2025-02-01') TO ('2025-03-01');
    """)

    op.execute("""
        CREATE TABLE monetization_events_2025_03 PARTITION OF monetization_events
            FOR VALUES FROM ('2025-03-01') TO ('2025-04-01');
    """)

    op.execute("""
        CREATE TABLE monetization_events_2025_04 PARTITION OF monetization_events
            FOR VALUES FROM ('2025-04-01') TO ('2025-05-01');
    """)

    op.execute("""
        CREATE TABLE monetization_events_2025_05 PARTITION OF monetization_events
            FOR VALUES FROM ('2025-05-01') TO ('2025-06-01');
    """)

    op.execute("""
        CREATE TABLE monetization_events_2025_06 PARTITION OF monetization_events
            FOR VALUES FROM ('2025-06-01') TO ('2025-07-01');
    """)

    # Recreate indexes
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


def downgrade() -> None:
    """
    Recreate non-partitioned table.
    WARNING: This will also lose data!
    """
    # Drop partitioned table
    op.execute("DROP TABLE IF EXISTS monetization_events CASCADE;")

    # Recreate non-partitioned version (from an001)
    op.execute("""
        CREATE TABLE monetization_events (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            event_id VARCHAR NOT NULL,
            user_id VARCHAR,
            session_token VARCHAR(255),

            -- Event Classification
            event_type VARCHAR(50) NOT NULL CHECK (event_type IN (
                'OFFER_VIEW', 'OFFER_CLICK', 'OFFER_ADD_TO_CART', 'OFFER_PURCHASE', 'OFFER_REFUND',
                'AD_IMPRESSION', 'AD_VIEWABLE_IMPRESSION', 'AD_CLICK',
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

    # Recreate indexes
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
