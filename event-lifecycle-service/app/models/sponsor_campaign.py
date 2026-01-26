# app/models/sponsor_campaign.py
"""
SponsorCampaign model - tracks email campaigns sent by sponsors to their leads.

Production-grade features:
- Audience filtering (all, hot, warm, new, contacted)
- Template variable substitution ({{name}}, {{company}}, etc.)
- Delivery tracking per lead
- Open rate and click tracking
- Async processing via Kafka
"""

import uuid
from sqlalchemy import Column, String, Integer, Boolean, DateTime, Text, ForeignKey, JSON, text
from sqlalchemy.orm import relationship
from app.db.base_class import Base


class SponsorCampaign(Base):
    __tablename__ = "sponsor_campaigns"

    id = Column(
        String, primary_key=True, default=lambda: f"spcmpn_{uuid.uuid4().hex[:12]}"
    )
    sponsor_id = Column(String, ForeignKey("sponsors.id"), nullable=False, index=True)
    event_id = Column(String, ForeignKey("events.id"), nullable=False, index=True)

    # Campaign Details
    name = Column(String(200), nullable=False)  # Internal name for tracking
    subject = Column(String(500), nullable=False)  # Email subject line
    message_body = Column(Text, nullable=False)  # Email body (supports {{variables}})

    # Audience Filtering
    audience_type = Column(String(20), nullable=False)
    # Options: 'all', 'hot', 'warm', 'cold', 'new', 'contacted', 'custom'
    audience_filter = Column(JSON, nullable=True, server_default='null')
    # For custom filters: {"intent_score_min": 50, "tags": ["enterprise"], ...}

    # Sending Metadata
    total_recipients = Column(Integer, nullable=False, server_default=text("0"))
    sent_count = Column(Integer, nullable=False, server_default=text("0"))
    delivered_count = Column(Integer, nullable=False, server_default=text("0"))
    failed_count = Column(Integer, nullable=False, server_default=text("0"))
    opened_count = Column(Integer, nullable=False, server_default=text("0"))
    clicked_count = Column(Integer, nullable=False, server_default=text("0"))

    # Status Tracking
    status = Column(String(20), nullable=False, server_default=text("'draft'"))
    # Options: 'draft', 'queued', 'sending', 'sent', 'failed', 'cancelled'

    # Scheduling
    scheduled_at = Column(DateTime(timezone=True), nullable=True)
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)

    # Audit
    created_by_user_id = Column(String, nullable=False)  # User who created campaign
    created_by_user_name = Column(String(200), nullable=True)  # Cached for display

    # Error Tracking
    error_message = Column(Text, nullable=True)  # If status = 'failed'

    # Metadata
    campaign_metadata = Column(JSON, nullable=True, server_default='{}')
    # For storing: template variables used, UTM parameters, etc.

    # Timestamps
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=text("NOW()"))
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=text("NOW()"))

    # Relationships
    sponsor = relationship("Sponsor", back_populates="campaigns")
    deliveries = relationship("CampaignDelivery", back_populates="campaign", cascade="all, delete-orphan")
