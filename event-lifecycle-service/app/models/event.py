# app/models/event.py
from sqlalchemy import Column, Integer, String, DateTime, Boolean, text
from sqlalchemy.orm import relationship
from app.db.base_class import Base
import uuid


class Event(Base):
    __tablename__ = "events"

    id = Column(
        String, primary_key=True, default=lambda: f"evt_{uuid.uuid4().hex[:12]}"
    )
    organization_id = Column(String, nullable=False, index=True)
    owner_id = Column(String, nullable=False, index=True)  # <-- ADD THIS LINE
    name = Column(String, nullable=False)
    version = Column(Integer, nullable=False, server_default=text("1"))
    description = Column(String, nullable=True)
    status = Column(String, nullable=False, default="draft")
    start_date = Column(DateTime, nullable=False)
    end_date = Column(DateTime, nullable=False)
    venue_id = Column(String, nullable=True)
    is_public = Column(Boolean, nullable=False, server_default=text("false"))
    is_archived = Column(Boolean, nullable=False, server_default=text("false"))
    createdAt = Column(DateTime, nullable=False, server_default=text("now()"))
    updatedAt = Column(DateTime, nullable=False, server_default=text("now()"))
    imageUrl = Column(String, nullable=True)

    # Relationship to registrations for eager loading
    registrations = relationship("Registration", back_populates="event")
