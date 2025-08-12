#app/models/session.py
from sqlalchemy import Column, String, DateTime, Boolean, ForeignKey, text
from sqlalchemy.orm import relationship
from app.db.base_class import Base
from app.models.session_speaker import session_speaker_association
import uuid


class Session(Base):
    __tablename__ = "sessions"

    id = Column(
        String, primary_key=True, default=lambda: f"evt_{uuid.uuid4().hex[:12]}"
    )
    event_id = Column(String, ForeignKey("events.id"), nullable=False, index=True)
    title = Column(String, nullable=False)
    start_time = Column(DateTime, nullable=False)
    end_time = Column(DateTime, nullable=False) 
    is_archived = Column(Boolean, nullable=False, server_default=text("false"))

    # This is the other "many" side of the relationship
    speakers = relationship(
        "Speaker", secondary=session_speaker_association, back_populates="sessions"
    )
