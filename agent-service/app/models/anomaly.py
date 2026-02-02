"""
Anomaly model for storing detected anomalies
"""
from sqlalchemy import Column, String, Float, TIMESTAMP, Index, JSON
from sqlalchemy.dialects.postgresql import UUID
from datetime import datetime
import uuid
from app.db.timescale import Base


class Anomaly(Base):
    """Stores detected anomalies in engagement"""
    __tablename__ = "anomalies"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = Column(String(255), nullable=False)  # Match SQL migration (VARCHAR)
    event_id = Column(String(255), nullable=False)    # Match SQL migration (VARCHAR)
    timestamp = Column(TIMESTAMP, nullable=False, default=datetime.utcnow)

    # Anomaly classification
    anomaly_type = Column(String(50), nullable=False)  # SUDDEN_DROP, GRADUAL_DECLINE, etc.
    severity = Column(String(20), nullable=False)  # WARNING, CRITICAL

    # Scores and metrics
    anomaly_score = Column(Float, nullable=False)
    current_engagement = Column(Float, nullable=False)
    expected_engagement = Column(Float, nullable=False)
    deviation = Column(Float, nullable=False)

    # Context
    signals = Column(JSON, nullable=True)
    extra_data = Column("metadata", JSON, nullable=True)  # Column named 'metadata' in DB, but 'extra_data' in Python

    __table_args__ = (
        Index('idx_anomaly_session', 'session_id', 'timestamp'),
        Index('idx_anomaly_severity', 'severity', 'timestamp'),
    )
