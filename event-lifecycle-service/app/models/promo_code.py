# app/models/promo_code.py
from sqlalchemy import Column, String, Boolean, DateTime, Integer, ForeignKey, Text, text
from sqlalchemy.dialects.postgresql import ARRAY
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
    description = Column(Text, nullable=True)
    discount_type = Column(String(20), nullable=False)  # 'percentage' or 'fixed'
    discount_value = Column(Integer, nullable=False)  # percentage (0-100) or fixed amount in cents
    currency = Column(String(3), server_default="USD", nullable=True)

    # Applicable ticket types (NULL = all ticket types)
    applicable_ticket_type_ids = Column(ARRAY(String), nullable=True)

    # Usage limits
    max_uses = Column(Integer, nullable=True)  # NULL = unlimited
    max_uses_per_user = Column(Integer, server_default="1", nullable=False)
    current_uses = Column(Integer, server_default="0", nullable=False)

    # Minimum requirements
    minimum_order_amount = Column(Integer, nullable=True)  # Minimum order total in cents
    minimum_tickets = Column(Integer, server_default="1", nullable=True)  # Minimum tickets in order

    # Legacy columns (kept for compatibility)
    times_used = Column(Integer, server_default="0", nullable=False)
    min_order_amount = Column(Integer, nullable=True)
    max_discount_amount = Column(Integer, nullable=True)

    # Validity period
    valid_from = Column(DateTime(timezone=True), nullable=True)
    valid_until = Column(DateTime(timezone=True), nullable=True)

    is_active = Column(Boolean, server_default=text("true"), nullable=False)
    created_by = Column(String, nullable=True)  # User ID who created
    created_at = Column(DateTime(timezone=True), server_default=text("now()"), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=text("now()"), nullable=False)

    # Relationships
    event = relationship("Event", foreign_keys=[event_id])
    usages = relationship("PromoCodeUsage", back_populates="promo_code")

    @property
    def is_currently_valid(self) -> bool:
        """Check if promo code is currently valid based on time window."""
        if not self.is_active:
            return False

        now = datetime.now(timezone.utc)

        if self.valid_from and now < self.valid_from:
            return False

        if self.valid_until and now > self.valid_until:
            return False

        return True

    @property
    def is_valid(self) -> bool:
        """Check if promo code is valid including usage limits."""
        if not self.is_currently_valid:
            return False

        if self.max_uses is not None and self.current_uses >= self.max_uses:
            return False

        return True

    @property
    def remaining_uses(self):
        """Calculate remaining uses, or None if unlimited."""
        if self.max_uses is None:
            return None
        return max(0, self.max_uses - self.current_uses)

    @property
    def discount_formatted(self) -> str:
        """Get formatted discount string (e.g., '20%' or '$10.00')."""
        if self.discount_type == "percentage":
            return f"{self.discount_value}%"
        else:
            # Format fixed amount in dollars
            dollars = self.discount_value / 100
            currency_symbol = "$" if self.currency == "USD" else self.currency
            return f"{currency_symbol}{dollars:.2f}"

    def calculate_discount(self, subtotal: int, applicable_subtotal: int = None) -> int:
        """Calculate the discount amount for a given subtotal.

        Args:
            subtotal: Total order amount in cents
            applicable_subtotal: Subtotal of items this code applies to (for partial discounts)
        """
        if not self.is_valid:
            return 0

        # Use minimum_order_amount if set, fallback to legacy min_order_amount
        min_amount = self.minimum_order_amount or self.min_order_amount
        if min_amount and subtotal < min_amount:
            return 0

        # Calculate discount based on applicable subtotal or full subtotal
        base_amount = applicable_subtotal if applicable_subtotal is not None else subtotal

        if self.discount_type == "percentage":
            discount = int(base_amount * self.discount_value / 100)
        else:  # fixed
            discount = self.discount_value

        # Apply max discount cap if set
        if self.max_discount_amount:
            discount = min(discount, self.max_discount_amount)

        # Don't discount more than the applicable subtotal
        return min(discount, base_amount)
