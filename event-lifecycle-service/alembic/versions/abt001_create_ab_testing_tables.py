"""Create A/B testing tables

Revision ID: abt001_ab_testing_tables
Revises: an003_events_partitioning
Create Date: 2025-12-31

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'abt001_ab_testing_tables'
down_revision = 'an003_events_partitioning'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create ab_tests table
    op.execute("""
        CREATE TABLE ab_tests (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            test_id VARCHAR(100) UNIQUE NOT NULL,
            name VARCHAR(255) NOT NULL,
            description TEXT,
            event_id VARCHAR NOT NULL,
            variants JSONB NOT NULL,
            is_active BOOLEAN NOT NULL DEFAULT false,
            target_audience JSONB,
            goal_metric VARCHAR(100) NOT NULL CHECK (goal_metric IN (
                'click_through',
                'purchase_conversion',
                'signup_conversion',
                'engagement_time',
                'custom'
            )),
            secondary_metrics JSONB,
            created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
            started_at TIMESTAMP WITH TIME ZONE,
            ended_at TIMESTAMP WITH TIME ZONE,
            min_sample_size INTEGER NOT NULL DEFAULT 100
        );
    """)

    # Create indexes on ab_tests
    op.execute("""
        CREATE INDEX idx_ab_tests_test_id ON ab_tests(test_id);
        CREATE INDEX idx_ab_tests_event_id ON ab_tests(event_id);
        CREATE INDEX idx_ab_tests_is_active ON ab_tests(is_active);
    """)

    # Create ab_test_events table
    op.execute("""
        CREATE TABLE ab_test_events (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            test_id VARCHAR(100) NOT NULL,
            event_id VARCHAR NOT NULL,
            user_id VARCHAR,
            session_token VARCHAR(255) NOT NULL,
            variant_id VARCHAR(100) NOT NULL,
            event_type VARCHAR(50) NOT NULL CHECK (event_type IN (
                'variant_view',
                'goal_conversion',
                'secondary_metric'
            )),
            goal_achieved BOOLEAN NOT NULL DEFAULT false,
            goal_value INTEGER,
            context JSONB,
            user_agent VARCHAR(500),
            created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
        );
    """)

    # Create indexes on ab_test_events for performance
    op.execute("""
        CREATE INDEX idx_ab_test_events_test_id ON ab_test_events(test_id);
        CREATE INDEX idx_ab_test_events_event_id ON ab_test_events(event_id);
        CREATE INDEX idx_ab_test_events_user_id ON ab_test_events(user_id);
        CREATE INDEX idx_ab_test_events_session ON ab_test_events(session_token);
        CREATE INDEX idx_ab_test_events_variant ON ab_test_events(variant_id);
        CREATE INDEX idx_ab_test_events_type ON ab_test_events(event_type);
        CREATE INDEX idx_ab_test_events_created ON ab_test_events(created_at);
        CREATE INDEX idx_ab_test_events_test_variant ON ab_test_events(test_id, variant_id);
    """)

    print("✅ Created ab_tests and ab_test_events tables")
    print("✅ Created indexes for A/B testing performance")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS ab_test_events CASCADE;")
    op.execute("DROP TABLE IF EXISTS ab_tests CASCADE;")
    print("✅ Dropped A/B testing tables")
