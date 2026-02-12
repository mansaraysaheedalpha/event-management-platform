# app/models/session_rsvp.py
"""
Session RSVP model for managing in-person session bookings.

Allows attendees to reserve spots for individual sessions,
enforcing capacity limits for in-person events.
"""

import uuid
from sqlalchemy import Column, String, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.sql import func

from app.db.base_class import Base


class SessionRsvp(Base):
    __tablename__ = "session_rsvps"

    id = Column(String, primary_key=True, default=lambda: f"srsvp_{uuid.uuid4().hex[:12]}")
    session_id = Column(String, ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(String, nullable=False, index=True)
    event_id = Column(String, ForeignKey("events.id", ondelete="CASCADE"), nullable=False, index=True)
    status = Column(String(20), nullable=False, server_default="CONFIRMED")  # CONFIRMED, CANCELLED
    rsvp_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    cancelled_at = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        UniqueConstraint('session_id', 'user_id', name='unique_session_rsvp_user'),
    )
