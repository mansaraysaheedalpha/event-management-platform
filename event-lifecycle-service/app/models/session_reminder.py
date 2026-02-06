"""Session Reminder model for tracking reminder emails sent to attendees."""

import uuid
from sqlalchemy import (
    Column,
    String,
    DateTime,
    ForeignKey,
    Text,
    Index,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import relationship
from app.db.base_class import Base


class SessionReminder(Base):
    """
    Tracks session reminder emails sent to registered attendees.

    Reminders are sent at configurable intervals before session start time
    (e.g., 15 minutes, 5 minutes) with magic link join buttons.
    """

    __tablename__ = "session_reminders"

    id = Column(
        String,
        primary_key=True,
        default=lambda: f"srem_{uuid.uuid4().hex[:12]}",
    )
    registration_id = Column(
        String,
        ForeignKey("registrations.id"),
        nullable=False,
        index=True,
    )
    session_id = Column(
        String,
        ForeignKey("sessions.id"),
        nullable=False,
        index=True,
    )
    user_id = Column(String, nullable=True, index=True)
    event_id = Column(String, nullable=False, index=True)

    # Reminder type: '15_MIN', '5_MIN', etc.
    reminder_type = Column(String(20), nullable=False)

    # Scheduling and status
    scheduled_at = Column(DateTime(timezone=True), nullable=False)
    sent_at = Column(DateTime(timezone=True), nullable=True)

    # Magic link tracking
    magic_link_token_jti = Column(String(255), nullable=True)

    # Email delivery status: QUEUED, SENT, DELIVERED, FAILED
    email_status = Column(
        String(20),
        nullable=False,
        server_default=text("'QUEUED'"),
    )
    error_message = Column(Text, nullable=True)

    # Relationships
    registration = relationship("Registration", backref="session_reminders")
    session = relationship("Session", backref="session_reminders")

    __table_args__ = (
        # Prevent duplicate reminders for same registration/session/type
        UniqueConstraint(
            "registration_id",
            "session_id",
            "reminder_type",
            name="uq_session_reminder_unique",
        ),
        # Optimized lookup indexes
        Index("idx_session_reminders_session", "session_id"),
        Index("idx_session_reminders_lookup", "session_id", "reminder_type"),
        Index("idx_session_reminders_pending", "email_status", "scheduled_at"),
    )

    def __repr__(self) -> str:
        return f"<SessionReminder {self.id} type={self.reminder_type} status={self.email_status}>"
