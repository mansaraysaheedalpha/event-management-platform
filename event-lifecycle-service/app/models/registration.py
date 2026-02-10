# app/models/registration.py
import uuid
from sqlalchemy import Column, String, ForeignKey, text, Enum, DateTime, Index
from sqlalchemy.orm import relationship
from app.db.base_class import Base


class Registration(Base):
    __tablename__ = "registrations"

    __table_args__ = (
        Index("ix_registrations_event_status_archived", "event_id", "status", "is_archived"),
        Index("ix_registrations_user_archived_status", "user_id", "is_archived", "status"),
    )

    id = Column(
        String, primary_key=True, default=lambda: f"reg_{uuid.uuid4().hex[:12]}"
    )
    event_id = Column(String, ForeignKey("events.id"), nullable=False, index=True)

    # This can be null if it's a guest registration without a formal user account
    user_id = Column(String, nullable=True, index=True)

    # We store guest info directly on the registration if no user_id is provided
    guest_email = Column(String, nullable=True, index=True)
    guest_name = Column(String, nullable=True)

    # NEW: A unique, human-readable ticket code for this registration
    ticket_code = Column(String, nullable=False, unique=True, index=True)

    # NEW: A timestamp to record when the ticket was validated/checked in
    checked_in_at = Column(DateTime(timezone=True), nullable=True)

    status = Column(
        Enum("confirmed", "cancelled", "checked_in", name="registration_status_enum"),
        nullable=False,
        server_default="confirmed",
    )
    is_archived = Column(String, nullable=False, server_default=text("false"))

    # Relationship to the Event model for eager loading
    event = relationship("Event", back_populates="registrations")
