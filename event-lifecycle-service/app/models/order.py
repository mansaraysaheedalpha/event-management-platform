# app/models/order.py
from sqlalchemy import Column, String, Boolean, DateTime, Integer, Text, ForeignKey, text, JSON
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from app.db.base_class import Base
import uuid
import hashlib
from datetime import datetime, timezone


class Order(Base):
    __tablename__ = "orders"

    id = Column(
        String, primary_key=True, default=lambda: f"ord_{uuid.uuid4().hex[:12]}"
    )
    order_number = Column(String(50), unique=True, nullable=False)
    event_id = Column(String, ForeignKey("events.id"), nullable=False, index=True)
    organization_id = Column(String, nullable=False, index=True)
    user_id = Column(String, nullable=True, index=True)

    # Guest information
    guest_email = Column(String(255), nullable=True)
    guest_first_name = Column(String(100), nullable=True)
    guest_last_name = Column(String(100), nullable=True)
    guest_phone = Column(String(50), nullable=True)

    # Order status
    status = Column(String(50), nullable=False, server_default="pending")
    # Values: 'pending', 'processing', 'completed', 'cancelled', 'refunded', 'partially_refunded', 'expired'

    # Financial
    currency = Column(String(3), nullable=False)
    subtotal = Column(Integer, nullable=False)  # In cents
    discount_amount = Column(Integer, server_default="0", nullable=False)
    tax_amount = Column(Integer, server_default="0", nullable=False)
    platform_fee = Column(Integer, server_default="0", nullable=False)
    total_amount = Column(Integer, nullable=False)

    # Stripe Connect fee fields
    subtotal_amount = Column(Integer, nullable=True)  # Original ticket prices before fee adjustments
    fee_absorption = Column(String(20), server_default="absorb", nullable=True)
    fee_breakdown_json = Column(JSONB, nullable=True)
    connected_account_id = Column(String(255), nullable=True)

    # Promo code
    promo_code_id = Column(String, ForeignKey("promo_codes.id"), nullable=True)

    # Payment tracking
    payment_provider = Column(String(50), nullable=True)
    payment_intent_id = Column(String(255), nullable=True, index=True)

    # Timestamps
    expires_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    cancelled_at = Column(DateTime(timezone=True), nullable=True)

    # Order metadata (renamed from 'metadata' which is reserved in SQLAlchemy)
    order_metadata = Column(JSONB, server_default="{}", nullable=True)
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=text("now()"), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=text("now()"), nullable=False)

    # Relationships
    event = relationship("Event", foreign_keys=[event_id])
    promo_code = relationship("PromoCode", foreign_keys=[promo_code_id])
    items = relationship("OrderItem", back_populates="order", cascade="all, delete-orphan")
    payments = relationship("Payment", back_populates="order")

    @staticmethod
    def generate_order_number(order_id: str) -> str:
        """Generate a human-readable order number."""
        year = datetime.now().year
        hash_part = hashlib.sha256(order_id.encode()).hexdigest()[:6].upper()
        return f"ORD-{year}-{hash_part}"

    @property
    def customer_email(self) -> str:
        """Get customer email (from user or guest)."""
        return self.guest_email or ""

    @property
    def customer_name(self) -> str:
        """Get customer full name (from user or guest)."""
        if self.guest_first_name or self.guest_last_name:
            return f"{self.guest_first_name or ''} {self.guest_last_name or ''}".strip()
        return ""

    @property
    def is_guest_order(self) -> bool:
        """Check if this is a guest checkout order."""
        return self.user_id is None

    @property
    def is_expired(self) -> bool:
        """Check if order has expired."""
        if self.status != "pending" or not self.expires_at:
            return False
        return datetime.now(timezone.utc) > self.expires_at

    @property
    def is_paid(self) -> bool:
        """Check if order has been paid."""
        return self.status in ("completed", "refunded", "partially_refunded")
