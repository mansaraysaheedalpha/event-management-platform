# app/models/waitlist_analytics.py
import uuid
from sqlalchemy import Column, String, ForeignKey, DateTime, Numeric, func, UniqueConstraint
from app.db.base_class import Base


class WaitlistAnalytics(Base):
    """
    Waitlist Analytics model for caching computed metrics.

    Purpose:
    - Cache expensive analytics calculations
    - Track metrics at event and session level
    - Avoid real-time computation for dashboard displays

    Common Metrics:
    - total_waitlist_entries: Total number of waitlist entries
    - active_waitlist_count: Number of users currently waiting
    - total_offers_issued: Total offers sent
    - total_offers_accepted: Total offers accepted
    - total_offers_declined: Total offers declined
    - total_offers_expired: Total offers that expired
    - acceptance_rate: Percentage of accepted offers
    - average_wait_time_minutes: Average time from join to offer
    """
    __tablename__ = "waitlist_analytics"

    id = Column(String, primary_key=True, default=lambda: f"wla_{uuid.uuid4().hex[:12]}")
    event_id = Column(String, ForeignKey("events.id", ondelete="CASCADE"), nullable=False, index=True)
    session_id = Column(String, ForeignKey("sessions.id", ondelete="CASCADE"), nullable=True, index=True)
    metric_name = Column(String(100), nullable=False, index=True)
    metric_value = Column(Numeric, nullable=False)
    calculated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), index=True)

    __table_args__ = (
        UniqueConstraint('event_id', 'session_id', 'metric_name', name='unique_event_session_metric'),
    )
