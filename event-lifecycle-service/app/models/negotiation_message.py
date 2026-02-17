# app/models/negotiation_message.py
# Schema only — no endpoints at launch
import uuid
from sqlalchemy import Column, String, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.base_class import Base


class NegotiationMessage(Base):
    __tablename__ = "negotiation_messages"

    id = Column(
        String, primary_key=True, default=lambda: f"ngm_{uuid.uuid4().hex[:12]}"
    )
    rfp_venue_id = Column(
        String,
        ForeignKey("rfp_venues.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    sender_type = Column(String, nullable=False)  # "organizer" | "venue"
    message_type = Column(String, nullable=False)  # "counter_offer" | "message" | "acceptance" | "rejection"
    content = Column(JSONB, nullable=True)

    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    # Relationships
    rfp_venue = relationship("RFPVenue", back_populates="negotiation_messages")
