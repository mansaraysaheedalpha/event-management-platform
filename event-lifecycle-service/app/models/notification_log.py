# app/models/notification_log.py
"""
Notification delivery tracking for RFP system.
Tracks email, WhatsApp, and in-app notifications.
"""
import uuid
from sqlalchemy import Column, String, Text, DateTime, ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func, text
from app.db.base_class import Base


class RFPNotification(Base):
    __tablename__ = "rfp_notifications"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    rfp_id = Column(
        String, ForeignKey("rfps.id", ondelete="CASCADE"), nullable=False, index=True
    )
    rfp_venue_id = Column(
        String, ForeignKey("rfp_venues.id", ondelete="CASCADE"), nullable=True, index=True
    )

    # Recipient details
    recipient_type = Column(String(20), nullable=False)  # 'venue_owner' or 'organizer'
    recipient_id = Column(String, nullable=False, index=True)  # user_id or organization_id
    recipient_identifier = Column(String(255), nullable=True)  # email or phone

    # Notification details
    channel = Column(String(20), nullable=False)  # 'email', 'whatsapp', 'inapp'
    event_type = Column(String(50), nullable=False, index=True)  # 'rfp.new_request', etc.

    # Delivery tracking
    status = Column(String(20), nullable=False, server_default=text("'pending'"))
    external_id = Column(String(255), nullable=True)  # Resend/AT message ID
    error_message = Column(Text, nullable=True)
    sent_at = Column(DateTime(timezone=True), nullable=True)
    delivered_at = Column(DateTime(timezone=True), nullable=True)

    # Timestamps
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    # Relationships
    rfp = relationship("RFP", backref="notifications")
    rfp_venue = relationship("RFPVenue", backref="notifications")

    __table_args__ = (
        Index("idx_rfp_notif_status_created", "status", "created_at"),
    )
