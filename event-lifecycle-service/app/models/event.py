# app/models/event.py
from sqlalchemy import Column, Integer, String, DateTime, Boolean, text, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from app.db.base_class import Base
import uuid
import enum


class EventType(str, enum.Enum):
    """Event type classification for virtual event support."""
    IN_PERSON = "IN_PERSON"
    VIRTUAL = "VIRTUAL"
    HYBRID = "HYBRID"


class Event(Base):
    __tablename__ = "events"

    id = Column(
        String, primary_key=True, default=lambda: f"evt_{uuid.uuid4().hex[:12]}"
    )
    organization_id = Column(String, nullable=False, index=True)
    owner_id = Column(String, nullable=False, index=True)
    name = Column(String, nullable=False)
    version = Column(Integer, nullable=False, server_default=text("1"))
    description = Column(String, nullable=True)
    status = Column(String, nullable=False, default="draft")
    start_date = Column(DateTime, nullable=False)
    end_date = Column(DateTime, nullable=False)
    venue_id = Column(String, ForeignKey("venues.id"), nullable=True)
    is_public = Column(Boolean, nullable=False, server_default=text("false"))
    is_archived = Column(Boolean, nullable=False, server_default=text("false"))
    createdAt = Column(DateTime, nullable=False, server_default=text("now()"))
    updatedAt = Column(DateTime, nullable=False, server_default=text("now()"))
    imageUrl = Column(String, nullable=True)

    # Virtual Event Support (Phase 1)
    event_type = Column(
        String,
        nullable=False,
        server_default=text("'IN_PERSON'"),
        index=True
    )
    virtual_settings = Column(
        JSONB,
        nullable=True,
        server_default=text("'{}'::jsonb"),
        comment="Virtual event configuration: streaming_provider, streaming_url, recording_enabled, auto_captions, lobby_enabled, lobby_video_url, max_concurrent_viewers, geo_restrictions"
    )

    # Event Capacity (nullable = unlimited)
    max_attendees = Column(Integer, nullable=True)

    # Relationships for eager loading
    registrations = relationship("Registration", back_populates="event")
    venue = relationship("Venue", foreign_keys=[venue_id])
    sessions = relationship("Session", back_populates="event")
