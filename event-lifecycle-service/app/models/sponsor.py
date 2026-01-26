# app/models/sponsor.py
"""
Sponsor model - represents a sponsor company at an event.

In the real world, sponsors are companies/organizations that pay to
have visibility and access at events. They typically get:
- Booth space (physical or virtual)
- Logo placement
- Access to attendee data (leads)
- Speaking opportunities
- Marketing materials distribution
"""

import uuid
from sqlalchemy import Column, String, Boolean, DateTime, JSON, ForeignKey, Text, text
from sqlalchemy.orm import relationship
from app.db.base_class import Base


class Sponsor(Base):
    __tablename__ = "sponsors"

    id = Column(
        String, primary_key=True, default=lambda: f"spon_{uuid.uuid4().hex[:12]}"
    )
    organization_id = Column(String, nullable=False, index=True)
    event_id = Column(String, ForeignKey("events.id"), nullable=False, index=True)
    tier_id = Column(String, ForeignKey("sponsor_tiers.id"), nullable=True, index=True)

    # Company Details
    company_name = Column(String(200), nullable=False)
    company_description = Column(Text, nullable=True)
    company_website = Column(String(500), nullable=True)
    company_logo_url = Column(String(500), nullable=True)

    # Contact Information (primary contact for the sponsor)
    contact_name = Column(String(200), nullable=True)
    contact_email = Column(String(255), nullable=True)
    contact_phone = Column(String(50), nullable=True)

    # Booth/Display Settings
    booth_number = Column(String(50), nullable=True)  # e.g., "A-15", "Hall B - 23"
    booth_description = Column(Text, nullable=True)  # What they're showcasing
    custom_booth_url = Column(String(500), nullable=True)  # Virtual booth link

    # Social Links (JSON object with platform keys)
    social_links = Column(JSON, nullable=True, server_default=text("'{}'"))
    # e.g., {"linkedin": "...", "twitter": "...", "facebook": "..."}

    # Marketing Assets (JSON array of asset objects)
    marketing_assets = Column(JSON, nullable=True, server_default=text("'[]'"))
    # e.g., [{"type": "brochure", "url": "...", "name": "Product Catalog"}]

    # Lead Capture Settings (can override tier settings)
    lead_capture_enabled = Column(Boolean, nullable=False, server_default=text("true"))
    lead_notification_email = Column(String(255), nullable=True)  # Email for lead alerts

    # Custom Fields (for event-specific sponsor data)
    custom_fields = Column(JSON, nullable=True, server_default=text("'{}'"))

    # Status
    is_active = Column(Boolean, nullable=False, server_default=text("true"))
    is_featured = Column(Boolean, nullable=False, server_default=text("false"))  # Show prominently
    is_archived = Column(Boolean, nullable=False, server_default=text("false"))

    # Timestamps
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=text("NOW()"))
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=text("NOW()"))

    # Relationships
    tier = relationship("SponsorTier", back_populates="sponsors")
    users = relationship("SponsorUser", back_populates="sponsor")
    invitations = relationship("SponsorInvitation", back_populates="sponsor")
    leads = relationship("SponsorLead", back_populates="sponsor")
    campaigns = relationship("SponsorCampaign", back_populates="sponsor")
    expo_booth = relationship("ExpoBooth", back_populates="sponsor", uselist=False)
