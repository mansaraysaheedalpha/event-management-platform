from sqlalchemy import Column, String, Float, Integer, Boolean, JSON, TIMESTAMP, Index
from sqlalchemy.dialects.postgresql import UUID
from datetime import datetime, timezone
import uuid
from app.db.timescale import Base


def utc_now_naive():
    """Return current UTC time as naive datetime (for TIMESTAMP WITHOUT TIME ZONE)"""
    return datetime.now(timezone.utc).replace(tzinfo=None)


class EngagementMetric(Base):
    """Stores engagement scores and signals over time"""
    __tablename__ = "engagement_metrics"

    time = Column(TIMESTAMP, primary_key=True, default=utc_now_naive)
    session_id = Column(String(255), primary_key=True)
    event_id = Column(String(255), nullable=False)
    engagement_score = Column(Float, nullable=False)
    chat_msgs_per_min = Column(Float)
    poll_participation = Column(Float)
    active_users = Column(Integer)
    reactions_per_min = Column(Float)
    user_leave_rate = Column(Float)
    extra_data = Column(JSON)

    __table_args__ = (
        Index('idx_session_time', 'session_id', 'time'),
        Index('idx_engagement_score', 'engagement_score'),
    )


class Intervention(Base):
    """Stores agent interventions and their outcomes"""
    __tablename__ = "interventions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = Column(String(255), nullable=False)
    timestamp = Column(TIMESTAMP, nullable=False, default=utc_now_naive)
    type = Column(String(50), nullable=False)  # POLL, CHAT_PROMPT, NUDGE, etc.
    confidence = Column(Float, nullable=False)
    reasoning = Column(String, nullable=True)
    outcome = Column(JSON, nullable=True)  # success, engagement_delta, etc.
    extra_data = Column(JSON, nullable=True)

    __table_args__ = (
        Index('idx_intervention_session', 'session_id', 'timestamp'),
    )


class AgentPerformance(Base):
    """Tracks agent performance metrics for learning"""
    __tablename__ = "agent_performance"

    time = Column(TIMESTAMP, primary_key=True, default=utc_now_naive)
    agent_id = Column(String(100), primary_key=True)
    intervention_type = Column(String(50), nullable=False)
    success = Column(Boolean, nullable=False)
    engagement_delta = Column(Float, nullable=True)
    confidence = Column(Float, nullable=True)
    session_id = Column(String(255), nullable=True)
    extra_data = Column(JSON, nullable=True)

    __table_args__ = (
        Index('idx_agent_performance', 'agent_id', 'time'),
    )
