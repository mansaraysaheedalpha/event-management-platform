# app/models/virtual_attendance.py
"""
Virtual Attendance Model - Tracks attendee participation in virtual sessions.

This model records when attendees join and leave virtual sessions,
enabling analytics on virtual event engagement.
"""
from sqlalchemy import Column, String, DateTime, Integer, ForeignKey, text, Index
from sqlalchemy.orm import relationship
from app.db.base_class import Base
from datetime import datetime
import uuid


class VirtualAttendance(Base):
    """
    Tracks virtual session attendance for analytics and reporting.

    Each record represents a single viewing session - when an attendee
    joins a virtual session, a record is created. When they leave,
    the record is updated with the leave time and duration.
    """
    __tablename__ = "virtual_attendance"

    id = Column(
        String, primary_key=True, default=lambda: f"va_{uuid.uuid4().hex[:12]}"
    )

    # Core relationships
    user_id = Column(String, nullable=False, index=True, comment="User who attended")
    session_id = Column(String, ForeignKey("sessions.id"), nullable=False, index=True)
    event_id = Column(String, ForeignKey("events.id"), nullable=False, index=True)

    # Timing
    joined_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        comment="When the user joined the virtual session"
    )
    left_at = Column(
        DateTime,
        nullable=True,
        comment="When the user left (null if still watching)"
    )

    # Computed/cached duration in seconds (for efficient queries)
    watch_duration_seconds = Column(
        Integer,
        nullable=True,
        comment="Total watch time in seconds (computed when user leaves)"
    )

    # Device/context info (optional, for analytics)
    device_type = Column(
        String,
        nullable=True,
        comment="Device type: desktop, mobile, tablet"
    )
    user_agent = Column(
        String,
        nullable=True,
        comment="Browser/app user agent string"
    )

    # Relationships
    session = relationship("Session", backref="virtual_attendances")
    event = relationship("Event", backref="virtual_attendances")

    # Indexes for common queries
    __table_args__ = (
        # For querying all attendance for a session
        Index('ix_virtual_attendance_session_joined', 'session_id', 'joined_at'),
        # For querying all attendance for an event
        Index('ix_virtual_attendance_event_joined', 'event_id', 'joined_at'),
        # For querying a user's attendance history
        Index('ix_virtual_attendance_user_event', 'user_id', 'event_id'),
    )

    def __repr__(self):
        return f"<VirtualAttendance(id={self.id}, user={self.user_id}, session={self.session_id})>"

    def calculate_duration(self) -> int:
        """Calculate watch duration in seconds."""
        if self.left_at and self.joined_at:
            return int((self.left_at - self.joined_at).total_seconds())
        return 0
