# app/models/sponsor_tier.py
"""
SponsorTier model - defines sponsorship levels for an event.

Real-world sponsorship tiers typically include:
- Platinum/Title: Highest tier with premium placement and benefits
- Gold: Second tier with prominent features
- Silver: Mid-tier with standard benefits
- Bronze: Entry-level tier with basic benefits
- Custom: Organizations can define their own tiers
"""

import uuid
from sqlalchemy import Column, String, Integer, Boolean, DateTime, JSON, ForeignKey, text
from sqlalchemy.orm import relationship
from app.db.base_class import Base


class SponsorTier(Base):
    __tablename__ = "sponsor_tiers"

    id = Column(
        String, primary_key=True, default=lambda: f"tier_{uuid.uuid4().hex[:12]}"
    )
    organization_id = Column(String, nullable=False, index=True)
    event_id = Column(String, ForeignKey("events.id"), nullable=False, index=True)

    # Tier Details
    name = Column(String(100), nullable=False)  # e.g., "Platinum", "Gold", "Silver"
    display_order = Column(Integer, nullable=False, server_default=text("0"))  # For sorting
    color = Column(String(7), nullable=True)  # Hex color code for UI

    # Benefits (JSON array of benefit strings)
    benefits = Column(JSON, nullable=False, server_default=text("'[]'"))

    # Booth/Display Settings
    booth_size = Column(String(20), nullable=True)  # e.g., "large", "medium", "small"
    logo_placement = Column(String(50), nullable=True)  # e.g., "header", "sidebar", "footer"
    max_representatives = Column(Integer, nullable=False, server_default=text("3"))  # Max users per sponsor

    # Lead Capture Settings
    can_capture_leads = Column(Boolean, nullable=False, server_default=text("true"))
    can_export_leads = Column(Boolean, nullable=False, server_default=text("true"))
    can_send_messages = Column(Boolean, nullable=False, server_default=text("false"))  # DM attendees

    # Pricing (for reference/display - actual payment handled separately)
    price_cents = Column(Integer, nullable=True)  # Price in cents
    currency = Column(String(3), nullable=True, server_default=text("'USD'"))

    # Status
    is_active = Column(Boolean, nullable=False, server_default=text("true"))

    # Timestamps
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=text("NOW()"))
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=text("NOW()"))

    # Relationships
    sponsors = relationship("Sponsor", back_populates="tier")
