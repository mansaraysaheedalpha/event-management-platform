# app/models/promo_code.py
from sqlalchemy import Column, String, Boolean, DateTime, Integer, ForeignKey, text
from sqlalchemy.orm import relationship
from app.db.base_class import Base
import uuid
from datetime import datetime, timezone


class PromoCode(Base):
    __tablename__ = "promo_codes"

    id = Column(
        String, primary_key=True, default=lambda: f"promo_{uuid.uuid4().hex[:12]}"
    )
    organization_id = Column(String, nullable=False, index=True)
    event_id = Column(String, ForeignKey("events.id", ondelete="CASCADE"), nullable=True, index=True)
    code = Column(String(50), nullable=False)
    discount_type = Column(String(20), nullable=False)  # 'percentage' or 'fixed'
    discount_value = Column(Integer, nullable=False)  # percentage (0-100) or fixed amount in cents
    currency = Column(String(3), server_default="USD", nullable=True)
    max_uses = Column(Integer, nullable=True)
    times_used = Column(Integer, server_default="0", nullable=False)
    min_order_amount = Column(Integer, nullable=True)
    max_discount_amount = Column(Integer, nullable=True)
    valid_from = Column(DateTime(timezone=True), nullable=True)
    valid_until = Column(DateTime(timezone=True), nullable=True)
    is_active = Column(Boolean, server_default=text("true"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=text("now()"), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=text("now()"), nullable=False)

    # Relationships
    event = relationship("Event", foreign_keys=[event_id])

    @property
    def is_valid(self):
        """Check if promo code is currently valid."""
        if not self.is_active:
            return False

        now = datetime.now(timezone.utc)

        if self.valid_from and now < self.valid_from:
            return False

        if self.valid_until and now > self.valid_until:
            return False

        if self.max_uses is not None and self.times_used >= self.max_uses:
            return False

        return True

    def calculate_discount(self, subtotal: int) -> int:
        """Calculate the discount amount for a given subtotal."""
        if not self.is_valid:
            return 0

        if self.min_order_amount and subtotal < self.min_order_amount:
            return 0

        if self.discount_type == "percentage":
            discount = int(subtotal * self.discount_value / 100)
        else:  # fixed
            discount = self.discount_value

        # Apply max discount cap if set
        if self.max_discount_amount:
            discount = min(discount, self.max_discount_amount)

        # Don't discount more than the subtotal
        return min(discount, subtotal)
