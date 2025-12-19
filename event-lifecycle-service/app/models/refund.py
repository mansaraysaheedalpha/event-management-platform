# app/models/refund.py
from sqlalchemy import Column, String, DateTime, Integer, Text, ForeignKey, text
from sqlalchemy.orm import relationship
from app.db.base_class import Base
import uuid


class Refund(Base):
    __tablename__ = "refunds"

    id = Column(
        String, primary_key=True, default=lambda: f"ref_{uuid.uuid4().hex[:12]}"
    )

    # Relationships
    payment_id = Column(String, ForeignKey("payments.id"), nullable=False, index=True)
    order_id = Column(String, ForeignKey("orders.id"), nullable=False, index=True)
    organization_id = Column(String, nullable=False, index=True)
    initiated_by_user_id = Column(String, nullable=True)  # Admin who initiated

    # Provider information
    provider_code = Column(String(50), nullable=False)
    provider_refund_id = Column(String(255), nullable=True)  # Provider's refund ID

    # Refund details
    status = Column(String(50), nullable=False)
    # Values: 'pending', 'processing', 'succeeded', 'failed', 'cancelled'

    reason = Column(String(100), nullable=False)
    # Values: 'requested_by_customer', 'duplicate', 'fraudulent', 'event_cancelled', 'other'
    reason_details = Column(Text, nullable=True)

    # Financial
    currency = Column(String(3), nullable=False)
    amount = Column(Integer, nullable=False)  # Refund amount in cents

    # Idempotency
    idempotency_key = Column(String(255), unique=True, nullable=True)

    # Failure information
    failure_code = Column(String(100), nullable=True)
    failure_message = Column(Text, nullable=True)

    # Timestamps
    processed_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=text("now()"), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=text("now()"), nullable=False)

    # Relationships
    payment = relationship("Payment", back_populates="refunds")
    order = relationship("Order", foreign_keys=[order_id])

    @property
    def is_successful(self) -> bool:
        """Check if refund was successful."""
        return self.status == "succeeded"

    @property
    def is_pending(self) -> bool:
        """Check if refund is still pending."""
        return self.status in ("pending", "processing")
