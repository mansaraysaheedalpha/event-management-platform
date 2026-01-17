#app/models/session.py
from sqlalchemy import Column, String, DateTime, Boolean, ForeignKey, text, Integer
from sqlalchemy.orm import relationship
from app.db.base_class import Base
from app.models.session_speaker import session_speaker_association
import uuid
import enum


class SessionType(str, enum.Enum):
    """Session type classification for virtual event support."""
    MAINSTAGE = "MAINSTAGE"
    BREAKOUT = "BREAKOUT"
    WORKSHOP = "WORKSHOP"
    NETWORKING = "NETWORKING"
    EXPO = "EXPO"


class Session(Base):
    __tablename__ = "sessions"

    id = Column(
        String, primary_key=True, default=lambda: f"ses_{uuid.uuid4().hex[:12]}"
    )
    event_id = Column(String, ForeignKey("events.id"), nullable=False, index=True)
    title = Column(String, nullable=False)
    start_time = Column(DateTime, nullable=False)
    end_time = Column(DateTime, nullable=False)
    is_archived = Column(Boolean, nullable=False, server_default=text("false"))

    # Interactive feature toggles (per-session control)
    chat_enabled = Column(Boolean, nullable=False, server_default=text("true"))
    qa_enabled = Column(Boolean, nullable=False, server_default=text("true"))
    polls_enabled = Column(Boolean, nullable=False, server_default=text("true"))
    breakout_enabled = Column(Boolean, nullable=False, server_default=text("false"), comment="Enable breakout rooms for this session")

    # Runtime state (controlled live by organizer/speaker)
    chat_open = Column(Boolean, nullable=False, server_default=text("false"))
    qa_open = Column(Boolean, nullable=False, server_default=text("false"))
    polls_open = Column(Boolean, nullable=False, server_default=text("false"))

    # Virtual Session Support (Phase 1)
    session_type = Column(
        String,
        nullable=False,
        server_default=text("'MAINSTAGE'"),
        index=True
    )
    virtual_room_id = Column(String, nullable=True, comment="External virtual room identifier")
    streaming_url = Column(String, nullable=True, comment="Live stream URL for virtual sessions")
    recording_url = Column(String, nullable=True, comment="Recording URL for on-demand playback")
    is_recordable = Column(Boolean, nullable=False, server_default=text("true"))
    requires_camera = Column(Boolean, nullable=False, server_default=text("false"))
    requires_microphone = Column(Boolean, nullable=False, server_default=text("false"))
    max_participants = Column(Integer, nullable=True, comment="Max participants for interactive sessions")
    broadcast_only = Column(Boolean, nullable=False, server_default=text("true"), comment="View-only sessions")

    # Green Room / Backstage Support (P1)
    green_room_enabled = Column(Boolean, nullable=False, server_default=text("true"), comment="Enable green room for speakers")
    green_room_opens_minutes_before = Column(Integer, nullable=False, server_default=text("15"), comment="Minutes before session green room opens")
    green_room_notes = Column(String, nullable=True, comment="Producer notes visible in green room")

    # Relationships
    speakers = relationship(
        "Speaker", secondary=session_speaker_association, back_populates="sessions"
    )
    event = relationship("Event", back_populates="sessions")
