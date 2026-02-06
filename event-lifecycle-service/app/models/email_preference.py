"""Email Preference model for user email opt-in/opt-out settings."""

import uuid
from sqlalchemy import (
    Column,
    String,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import relationship
from app.db.base_class import Base


class EmailPreference(Base):
    """
    User email preferences for different email types.

    Preferences can be set globally (event_id=None) or per-event.
    Event-specific preferences override global preferences.
    """

    __tablename__ = "email_preferences"

    id = Column(
        String,
        primary_key=True,
        default=lambda: f"epref_{uuid.uuid4().hex[:12]}",
    )
    user_id = Column(String, nullable=False, index=True)
    event_id = Column(
        String,
        ForeignKey("events.id", ondelete="CASCADE"),
        nullable=True,  # NULL = global preference
        index=True,
    )

    # Email type preferences
    pre_event_agenda = Column(
        Boolean,
        nullable=False,
        server_default=text("true"),
    )
    pre_event_networking = Column(
        Boolean,
        nullable=False,
        server_default=text("true"),
    )
    session_reminders = Column(
        Boolean,
        nullable=False,
        server_default=text("true"),
    )

    # Timestamps
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("NOW()"),
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("NOW()"),
    )

    # Relationships
    event = relationship("Event", backref="email_preferences")

    __table_args__ = (
        # One preference record per user per event (or global)
        UniqueConstraint(
            "user_id",
            "event_id",
            name="uq_email_pref_user_event",
        ),
        Index("idx_email_preferences_user", "user_id"),
        Index("idx_email_preferences_event", "event_id"),
    )

    def __repr__(self) -> str:
        scope = f"event={self.event_id}" if self.event_id else "global"
        return f"<EmailPreference {self.id} user={self.user_id} {scope}>"
