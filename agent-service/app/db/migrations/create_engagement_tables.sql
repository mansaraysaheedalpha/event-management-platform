-- Migration: Create engagement tables for agent-service
-- Run this manually if using standard PostgreSQL (without TimescaleDB)
--
-- For Render PostgreSQL, run via: psql $DATABASE_URL -f create_engagement_tables.sql
-- Or connect via Render dashboard and run the SQL

-- Create engagement_metrics table
CREATE TABLE IF NOT EXISTS engagement_metrics (
    time TIMESTAMP WITHOUT TIME ZONE NOT NULL,
    session_id VARCHAR(255) NOT NULL,
    event_id VARCHAR(255) NOT NULL,
    engagement_score FLOAT NOT NULL,
    chat_msgs_per_min FLOAT,
    poll_participation FLOAT,
    active_users INTEGER,
    reactions_per_min FLOAT,
    user_leave_rate FLOAT,
    extra_data JSONB,
    PRIMARY KEY (time, session_id)
);

-- Create indexes for efficient queries
CREATE INDEX IF NOT EXISTS idx_engagement_session_time ON engagement_metrics(session_id, time);
CREATE INDEX IF NOT EXISTS idx_engagement_score ON engagement_metrics(engagement_score);
CREATE INDEX IF NOT EXISTS idx_engagement_event ON engagement_metrics(event_id, time);

-- Create interventions table
CREATE TABLE IF NOT EXISTS interventions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id VARCHAR(255) NOT NULL,
    timestamp TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
    type VARCHAR(50) NOT NULL,
    confidence FLOAT NOT NULL,
    reasoning TEXT,
    outcome JSONB,
    extra_data JSONB
);

CREATE INDEX IF NOT EXISTS idx_intervention_session ON interventions(session_id, timestamp);
CREATE INDEX IF NOT EXISTS idx_intervention_type ON interventions(type);

-- Create agent_performance table
CREATE TABLE IF NOT EXISTS agent_performance (
    time TIMESTAMP WITHOUT TIME ZONE NOT NULL,
    agent_id VARCHAR(100) NOT NULL,
    intervention_type VARCHAR(50) NOT NULL,
    success BOOLEAN NOT NULL,
    engagement_delta FLOAT,
    confidence FLOAT,
    session_id VARCHAR(255),
    extra_data JSONB,
    PRIMARY KEY (time, agent_id)
);

CREATE INDEX IF NOT EXISTS idx_agent_performance ON agent_performance(agent_id, time);

-- Create anomalies table
CREATE TABLE IF NOT EXISTS anomalies (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id VARCHAR(255) NOT NULL,
    event_id VARCHAR(255) NOT NULL,
    timestamp TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
    anomaly_type VARCHAR(50) NOT NULL,
    severity VARCHAR(20) NOT NULL,
    anomaly_score FLOAT,
    current_engagement FLOAT,
    expected_engagement FLOAT,
    deviation FLOAT,
    signals JSONB,
    metadata JSONB
);

CREATE INDEX IF NOT EXISTS idx_anomaly_session ON anomalies(session_id, timestamp);
CREATE INDEX IF NOT EXISTS idx_anomaly_severity ON anomalies(severity);

-- Create event_agent_settings table
CREATE TABLE IF NOT EXISTS event_agent_settings (
    event_id VARCHAR(255) PRIMARY KEY,
    agent_enabled BOOLEAN NOT NULL DEFAULT true,
    agent_mode VARCHAR(20) NOT NULL DEFAULT 'SEMI_AUTO',
    confidence_threshold FLOAT DEFAULT 0.75,
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW()
);

-- Grant permissions (adjust role name as needed for your setup)
-- GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO your_db_user;

-- Verify tables were created
SELECT table_name FROM information_schema.tables
WHERE table_schema = 'public'
AND table_name IN ('engagement_metrics', 'interventions', 'agent_performance', 'anomalies', 'event_agent_settings');
