"""Pre-Event Email model for tracking pre-event engagement emails."""

import uuid
from sqlalchemy import (
    Column,
    String,
    DateTime,
    Date,
    ForeignKey,
    Text,
    Index,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import relationship
from app.db.base_class import Base


class PreEventEmail(Base):
    """
    Tracks pre-event engagement emails sent to registered attendees.

    Pre-event emails are sent 24 hours before events start and include:
    - AGENDA: Personalized session recommendations and expo booths
    - NETWORKING: People-to-meet recommendations with conversation starters
    """

    __tablename__ = "pre_event_emails"

    id = Column(
        String,
        primary_key=True,
        default=lambda: f"pee_{uuid.uuid4().hex[:12]}",
    )
    registration_id = Column(
        String,
        ForeignKey("registrations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    event_id = Column(
        String,
        ForeignKey("events.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id = Column(String, nullable=True, index=True)

    # Email type: AGENDA, NETWORKING
    email_type = Column(String(20), nullable=False)

    # Date for deduplication (prevents sending same email twice for same event)
    email_date = Column(Date, nullable=False)

    # Scheduling and status
    scheduled_at = Column(DateTime(timezone=True), nullable=False)
    sent_at = Column(DateTime(timezone=True), nullable=True)

    # Email delivery tracking
    email_status = Column(
        String(20),
        nullable=False,
        server_default=text("'QUEUED'"),
    )
    resend_message_id = Column(String(255), nullable=True)
    error_message = Column(Text, nullable=True)

    # Relationships
    registration = relationship("Registration", backref="pre_event_emails")
    event = relationship("Event", backref="pre_event_emails")

    __table_args__ = (
        # Prevent duplicate emails for same registration/event/type/date
        UniqueConstraint(
            "registration_id",
            "event_id",
            "email_type",
            "email_date",
            name="uq_pre_event_email",
        ),
        # Optimized lookup indexes
        Index("idx_pre_event_emails_event", "event_id"),
        Index("idx_pre_event_emails_registration", "registration_id"),
        Index("idx_pre_event_emails_pending", "email_status", "scheduled_at"),
        Index("idx_pre_event_emails_lookup", "event_id", "email_type", "email_date"),
    )

    def __repr__(self) -> str:
        return f"<PreEventEmail {self.id} type={self.email_type} status={self.email_status}>"
