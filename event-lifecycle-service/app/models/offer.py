# app/models/offer.py
import uuid
from sqlalchemy import Column, String, text, ForeignKey, Float, DateTime
from app.db.base_class import Base


class Offer(Base):
    __tablename__ = "offers"

    id = Column(
        String, primary_key=True, default=lambda: f"offer_{uuid.uuid4().hex[:12]}"
    )
    organization_id = Column(String, nullable=False, index=True)
    event_id = Column(String, ForeignKey("events.id"), nullable=False, index=True)
    title = Column(String, nullable=False)
    description = Column(String, nullable=True)
    price = Column(Float, nullable=False)
    original_price = Column(Float, nullable=True)
    currency = Column(String, nullable=False, default="USD")
    offer_type = Column(String, nullable=False)  # e.g., TICKET_UPGRADE, MERCHANDISE
    image_url = Column(String, nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=True)
    is_archived = Column(String, nullable=False, server_default=text("false"))
