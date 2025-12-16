#app/models/session.py
from sqlalchemy import Column, String, DateTime, Boolean, ForeignKey, text
from sqlalchemy.orm import relationship
from app.db.base_class import Base
from app.models.session_speaker import session_speaker_association
import uuid


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

    # Runtime state (controlled live by organizer/speaker)
    chat_open = Column(Boolean, nullable=False, server_default=text("false"))
    qa_open = Column(Boolean, nullable=False, server_default=text("false"))
    polls_open = Column(Boolean, nullable=False, server_default=text("false"))

    # Relationships
    speakers = relationship(
        "Speaker", secondary=session_speaker_association, back_populates="sessions"
    )
    event = relationship("Event", back_populates="sessions")
