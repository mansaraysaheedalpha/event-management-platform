# app/models/payment_audit_log.py
from sqlalchemy import Column, String, DateTime, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from app.db.base_class import Base
import uuid


class PaymentAuditLog(Base):
    __tablename__ = "payment_audit_log"

    id = Column(
        String, primary_key=True, default=lambda: f"pal_{uuid.uuid4().hex[:12]}"
    )

    # What happened
    action = Column(String(100), nullable=False)
    # Values: 'order.created', 'payment.initiated', 'payment.succeeded', 'payment.failed',
    #         'refund.initiated', 'refund.succeeded', 'refund.failed', 'webhook.received', etc.

    # Who did it
    actor_type = Column(String(50), nullable=False)  # 'user', 'system', 'webhook', 'admin'
    actor_id = Column(String, nullable=True)  # User ID if applicable
    actor_ip = Column(String(45), nullable=True)
    actor_user_agent = Column(Text, nullable=True)

    # What was affected
    entity_type = Column(String(50), nullable=False)  # 'order', 'payment', 'refund'
    entity_id = Column(String, nullable=False)

    # Change details
    previous_state = Column(JSONB, nullable=True)
    new_state = Column(JSONB, nullable=True)
    change_details = Column(JSONB, nullable=True)  # Specific fields that changed

    # Context
    organization_id = Column(String, nullable=True)
    event_id = Column(String, nullable=True)
    request_id = Column(String(100), nullable=True)  # Correlation ID for request tracing

    # Immutable timestamp
    created_at = Column(DateTime(timezone=True), server_default=text("now()"), nullable=False)
