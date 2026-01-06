-- Add agent settings to events table
-- This allows organizers to configure agent behavior per event

-- Add columns to events table (assuming you have one in the main DB)
-- Note: This would be executed in the main event-lifecycle-service database

-- For now, we'll store agent settings in our engagement_conductor database
-- and sync based on event_id

CREATE TABLE IF NOT EXISTS event_agent_settings (
    event_id VARCHAR(255) PRIMARY KEY,

    -- Agent configuration
    agent_enabled BOOLEAN DEFAULT TRUE,
    agent_mode VARCHAR(20) DEFAULT 'SEMI_AUTO', -- MANUAL, SEMI_AUTO, AUTO

    -- Thresholds
    auto_approve_threshold FLOAT DEFAULT 0.75, -- For SEMI_AUTO mode
    min_confidence_threshold FLOAT DEFAULT 0.50, -- Don't suggest below this

    -- Intervention preferences
    allowed_interventions TEXT[], -- Array of allowed intervention types
    max_interventions_per_hour INTEGER DEFAULT 3,

    -- Notification settings
    notify_on_anomaly BOOLEAN DEFAULT TRUE,
    notify_on_intervention BOOLEAN DEFAULT TRUE,
    notification_emails TEXT[],

    -- Metadata
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Create index for quick lookups
CREATE INDEX IF NOT EXISTS idx_event_agent_settings_event_id ON event_agent_settings(event_id);

-- Insert default settings for existing events
-- This is a one-time migration
INSERT INTO event_agent_settings (event_id, agent_enabled, agent_mode)
SELECT DISTINCT event_id, TRUE, 'SEMI_AUTO'
FROM engagement_metrics
WHERE event_id IS NOT NULL
ON CONFLICT (event_id) DO NOTHING;

-- Add trigger to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_event_agent_settings_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER event_agent_settings_updated_at
    BEFORE UPDATE ON event_agent_settings
    FOR EACH ROW
    EXECUTE FUNCTION update_event_agent_settings_updated_at();
