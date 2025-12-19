# app/models/payment.py
from sqlalchemy import Column, String, DateTime, Integer, Text, ForeignKey, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from app.db.base_class import Base
import uuid


class Payment(Base):
    __tablename__ = "payments"

    id = Column(
        String, primary_key=True, default=lambda: f"pay_{uuid.uuid4().hex[:12]}"
    )
    order_id = Column(String, ForeignKey("orders.id"), nullable=False, index=True)
    organization_id = Column(String, nullable=False, index=True)

    # Provider information
    provider_code = Column(String(50), nullable=False)  # 'stripe', 'paystack', etc.
    provider_payment_id = Column(String(255), nullable=False, index=True)  # Provider's payment/charge ID
    provider_intent_id = Column(String(255), nullable=True)  # Payment intent ID if applicable

    # Payment details
    status = Column(String(50), nullable=False)
    # Values: 'pending', 'processing', 'succeeded', 'failed', 'cancelled', 'refunded', 'partially_refunded'

    # Financial
    currency = Column(String(3), nullable=False)
    amount = Column(Integer, nullable=False)  # Amount charged in cents
    amount_refunded = Column(Integer, server_default="0", nullable=False)  # Total refunded amount
    provider_fee = Column(Integer, server_default="0", nullable=False)  # Stripe/Paystack fee
    net_amount = Column(Integer, nullable=False)  # amount - provider_fee

    # Payment method details (non-sensitive only)
    payment_method_type = Column(String(50), nullable=True)  # 'card', 'bank_transfer', etc.
    payment_method_details = Column(JSONB, server_default="{}", nullable=True)
    # Example: {"brand": "visa", "last4": "4242", "exp_month": 12, "exp_year": 2025}

    # Failure information
    failure_code = Column(String(100), nullable=True)
    failure_message = Column(Text, nullable=True)

    # Idempotency
    idempotency_key = Column(String(255), unique=True, nullable=True)

    # Risk assessment
    risk_score = Column(Integer, nullable=True)  # 0-100
    risk_level = Column(String(20), nullable=True)  # 'normal', 'elevated', 'high'

    # Timestamps
    processed_at = Column(DateTime(timezone=True), nullable=True)

    # Metadata from provider
    provider_metadata = Column(JSONB, server_default="{}", nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=text("now()"), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=text("now()"), nullable=False)

    # Relationships
    order = relationship("Order", back_populates="payments")
    refunds = relationship("Refund", back_populates="payment")

    @property
    def is_successful(self) -> bool:
        """Check if payment was successful."""
        return self.status == "succeeded"

    @property
    def is_refundable(self) -> bool:
        """Check if payment can be refunded."""
        return self.status == "succeeded" and self.amount > self.amount_refunded

    @property
    def refundable_amount(self) -> int:
        """Get the amount that can still be refunded."""
        if not self.is_refundable:
            return 0
        return self.amount - self.amount_refunded
