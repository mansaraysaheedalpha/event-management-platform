# app/models/campaign_delivery.py
"""
CampaignDelivery model - tracks delivery status for each recipient in a campaign.

This enables:
- Per-lead delivery confirmation
- Individual open/click tracking
- Resend failures for specific recipients
- Detailed campaign analytics
"""

import uuid
from sqlalchemy import Column, String, Boolean, DateTime, Text, ForeignKey, Integer, text
from sqlalchemy.orm import relationship
from app.db.base_class import Base


class CampaignDelivery(Base):
    __tablename__ = "campaign_deliveries"

    id = Column(
        String, primary_key=True, default=lambda: f"spdlvr_{uuid.uuid4().hex[:12]}"
    )
    campaign_id = Column(String, ForeignKey("sponsor_campaigns.id"), nullable=False, index=True)
    lead_id = Column(String, ForeignKey("sponsor_leads.id"), nullable=False, index=True)

    # Recipient Details (denormalized for quick access)
    recipient_email = Column(String(255), nullable=False)
    recipient_name = Column(String(200), nullable=True)

    # Personalized Content (what was actually sent)
    personalized_subject = Column(String(500), nullable=False)
    personalized_body = Column(Text, nullable=False)

    # Delivery Status
    status = Column(String(20), nullable=False, server_default=text("'pending'"))
    # Options: 'pending', 'sent', 'delivered', 'bounced', 'failed', 'spam'

    # Email Service Provider Response
    provider_message_id = Column(String(500), nullable=True)  # Resend message ID
    provider_response = Column(Text, nullable=True)  # Full API response for debugging

    # Engagement Tracking
    opened_at = Column(DateTime(timezone=True), nullable=True)
    opened_count = Column(Integer, nullable=False, server_default=text("0"))
    first_click_at = Column(DateTime(timezone=True), nullable=True)
    click_count = Column(Integer, nullable=False, server_default=text("0"))

    # Error Tracking
    error_message = Column(Text, nullable=True)
    retry_count = Column(Integer, nullable=False, server_default=text("0"))
    last_retry_at = Column(DateTime(timezone=True), nullable=True)

    # Timestamps
    queued_at = Column(DateTime(timezone=True), nullable=False, server_default=text("NOW()"))
    sent_at = Column(DateTime(timezone=True), nullable=True)
    delivered_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    campaign = relationship("SponsorCampaign", back_populates="deliveries")
    lead = relationship("SponsorLead")
