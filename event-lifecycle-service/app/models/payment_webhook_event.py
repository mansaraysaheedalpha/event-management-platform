# app/models/payment_webhook_event.py
from sqlalchemy import Column, String, Boolean, DateTime, Integer, Text, ForeignKey, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from app.db.base_class import Base
import uuid


class PaymentWebhookEvent(Base):
    __tablename__ = "payment_webhook_events"

    id = Column(
        String, primary_key=True, default=lambda: f"whe_{uuid.uuid4().hex[:12]}"
    )

    # Provider information
    provider_code = Column(String(50), nullable=False)
    provider_event_id = Column(String(255), nullable=False)  # Provider's event ID
    provider_event_type = Column(String(100), nullable=False)  # e.g., 'payment_intent.succeeded'

    # Processing status
    status = Column(String(50), nullable=False, server_default="pending")
    # Values: 'pending', 'processing', 'processed', 'failed', 'skipped'

    # Payload
    payload = Column(JSONB, nullable=False)

    # Signature verification
    signature_verified = Column(Boolean, server_default=text("false"), nullable=False)

    # Processing details
    processed_at = Column(DateTime(timezone=True), nullable=True)
    processing_error = Column(Text, nullable=True)
    retry_count = Column(Integer, server_default="0", nullable=False)
    next_retry_at = Column(DateTime(timezone=True), nullable=True)

    # Related entities (populated during processing)
    related_payment_id = Column(String, ForeignKey("payments.id"), nullable=True)
    related_order_id = Column(String, ForeignKey("orders.id"), nullable=True)
    related_refund_id = Column(String, ForeignKey("refunds.id"), nullable=True)

    # Request metadata
    received_at = Column(DateTime(timezone=True), server_default=text("now()"), nullable=False)
    ip_address = Column(String(45), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=text("now()"), nullable=False)

    # Relationships
    payment = relationship("Payment", foreign_keys=[related_payment_id])
    order = relationship("Order", foreign_keys=[related_order_id])
    refund = relationship("Refund", foreign_keys=[related_refund_id])

    @property
    def is_processed(self) -> bool:
        """Check if event has been processed."""
        return self.status == "processed"

    @property
    def is_retryable(self) -> bool:
        """Check if event can be retried."""
        return self.status == "failed" and self.retry_count < 5

    @property
    def max_retries_exceeded(self) -> bool:
        """Check if max retries have been exceeded."""
        return self.retry_count >= 5
