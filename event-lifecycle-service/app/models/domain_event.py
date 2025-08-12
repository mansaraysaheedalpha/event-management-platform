#/app/models/domain_event.py
import uuid
from sqlalchemy import Column, String, DateTime, ForeignKey, func
from sqlalchemy.dialects.postgresql import JSONB
from app.db.base_class import Base


class DomainEvent(Base):
    __tablename__ = "domain_events"

    id = Column(String, primary_key=True, default=lambda: f"de_{uuid.uuid4().hex[:12]}")
    event_id = Column(String, ForeignKey("events.id"), nullable=False, index=True)
    event_type = Column(
        String, nullable=False
    )  # e.g., "EventUpdated", "EventPublished"
    timestamp = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    user_id = Column(String, nullable=True)  # The user who initiated the event
    data = Column(
        JSONB, nullable=True
    )  # The payload of the event, e.g., {"old_name": "...", "new_name": "..."}
