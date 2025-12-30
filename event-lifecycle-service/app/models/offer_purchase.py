# app/models/offer_purchase.py
import uuid
from sqlalchemy import Column, String, Integer, Float, DateTime, ForeignKey, text
from sqlalchemy.orm import relationship
from app.db.base_class import Base


class OfferPurchase(Base):
    __tablename__ = "offer_purchases"

    id = Column(
        String, primary_key=True, default=lambda: f"ofp_{uuid.uuid4().hex[:12]}"
    )
    offer_id = Column(String, ForeignKey("offers.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(String, nullable=False, index=True)
    order_id = Column(String, nullable=True, index=True)

    # Purchase Details
    quantity = Column(Integer, nullable=False, server_default=text("1"))
    unit_price = Column(Float, nullable=False)
    total_price = Column(Float, nullable=False)
    currency = Column(String(3), nullable=False, server_default=text("'USD'"))

    # Fulfillment
    fulfillment_status = Column(String(50), nullable=False, server_default=text("'PENDING'"))
    fulfillment_type = Column(String(50), nullable=True)  # DIGITAL, PHYSICAL, SERVICE, TICKET
    digital_content_url = Column(String, nullable=True)
    access_code = Column(String(255), nullable=True)
    tracking_number = Column(String(255), nullable=True)

    # Timestamps
    purchased_at = Column(DateTime(timezone=True), nullable=False, server_default=text("NOW()"))
    fulfilled_at = Column(DateTime(timezone=True), nullable=True)
    refunded_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    offer = relationship("Offer", back_populates="purchases")
