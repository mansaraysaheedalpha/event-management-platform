"""
EventAgentSettings model for per-event agent configuration
"""
from sqlalchemy import Column, String, Float, Boolean, Integer, TIMESTAMP, ARRAY
from datetime import datetime, timezone
from app.db.timescale import Base


class EventAgentSettings(Base):
    """
    Stores agent configuration settings per event.

    Allows organizers to customize agent behavior including:
    - Operating mode (MANUAL, SEMI_AUTO, AUTO)
    - Confidence thresholds
    - Allowed intervention types
    - Rate limiting
    - Notification preferences
    """
    __tablename__ = "event_agent_settings"

    event_id = Column(String(255), primary_key=True)

    # Agent configuration
    agent_enabled = Column(Boolean, default=True, nullable=False)
    agent_mode = Column(String(20), default='SEMI_AUTO', nullable=False)  # MANUAL, SEMI_AUTO, AUTO

    # Thresholds
    auto_approve_threshold = Column(Float, default=0.75, nullable=False)  # For SEMI_AUTO mode
    min_confidence_threshold = Column(Float, default=0.50, nullable=False)  # Don't suggest below this

    # Intervention preferences
    allowed_interventions = Column(ARRAY(String), nullable=True)  # Array of allowed intervention types
    max_interventions_per_hour = Column(Integer, default=3, nullable=False)

    # Notification settings
    notify_on_anomaly = Column(Boolean, default=True, nullable=False)
    notify_on_intervention = Column(Boolean, default=True, nullable=False)
    notification_emails = Column(ARRAY(String), nullable=True)

    # Metadata
    created_at = Column(TIMESTAMP(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(TIMESTAMP(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    def __repr__(self):
        return f"<EventAgentSettings(event_id={self.event_id}, mode={self.agent_mode}, enabled={self.agent_enabled})>"
