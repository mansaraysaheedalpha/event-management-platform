# app/models/sponsor_lead.py
"""
SponsorLead model - tracks leads captured for sponsors.

In the real world, sponsors capture leads through various interactions:
- Booth visits (QR scan, badge scan)
- Content engagement (downloading materials, watching demos)
- Session attendance (if sponsor has a speaking slot)
- Contest/giveaway participation
- Direct requests (attendee requests contact)

Lead scoring is typically based on:
- Number and type of interactions
- Time spent engaging
- Content downloaded
- Direct interest expressed
"""

import uuid
from sqlalchemy import Column, String, Integer, Boolean, DateTime, JSON, ForeignKey, Text, text
from sqlalchemy.orm import relationship
from app.db.base_class import Base


class SponsorLead(Base):
    __tablename__ = "sponsor_leads"

    id = Column(
        String, primary_key=True, default=lambda: f"splead_{uuid.uuid4().hex[:12]}"
    )
    sponsor_id = Column(String, ForeignKey("sponsors.id"), nullable=False, index=True)
    event_id = Column(String, ForeignKey("events.id"), nullable=False, index=True)

    # Lead Details (attendee who interacted)
    user_id = Column(String, nullable=False, index=True)  # Attendee's user ID
    user_name = Column(String(200), nullable=True)  # Cached for quick display
    user_email = Column(String(255), nullable=True)  # Cached for quick display
    user_company = Column(String(200), nullable=True)  # Attendee's company
    user_title = Column(String(200), nullable=True)  # Attendee's job title

    # Lead Scoring
    intent_score = Column(Integer, nullable=False, server_default=text("0"))  # 0-100
    # Score calculated based on interactions:
    # - Booth visit: +10
    # - Content download: +15
    # - Demo watched: +20
    # - Direct request: +30
    # - Time spent (per minute): +2
    # - Repeat visit: +5

    intent_level = Column(String(10), nullable=False, server_default=text("'cold'"))
    # Options: 'hot' (70+), 'warm' (40-69), 'cold' (0-39)

    # Interaction Tracking
    first_interaction_at = Column(DateTime(timezone=True), nullable=False, server_default=text("NOW()"))
    last_interaction_at = Column(DateTime(timezone=True), nullable=False, server_default=text("NOW()"))
    interaction_count = Column(Integer, nullable=False, server_default=text("1"))

    # Interaction History (JSON array of interaction objects)
    interactions = Column(JSON, nullable=False, server_default=text("'[]'"))
    # e.g., [
    #   {"type": "booth_visit", "timestamp": "...", "duration_seconds": 120},
    #   {"type": "content_download", "timestamp": "...", "content_name": "Product Brochure"},
    #   {"type": "demo_request", "timestamp": "...", "notes": "Interested in enterprise plan"}
    # ]

    # Contact Preferences
    contact_requested = Column(Boolean, nullable=False, server_default=text("false"))
    contact_notes = Column(Text, nullable=True)  # Notes from attendee
    preferred_contact_method = Column(String(20), nullable=True)  # email, phone, linkedin

    # Follow-up Status
    follow_up_status = Column(String(20), nullable=False, server_default=text("'new'"))
    # Options: 'new', 'contacted', 'qualified', 'not_interested', 'converted'
    follow_up_notes = Column(Text, nullable=True)
    followed_up_at = Column(DateTime(timezone=True), nullable=True)
    followed_up_by_user_id = Column(String, nullable=True)

    # Tags for categorization (JSON array of strings)
    tags = Column(JSON, nullable=True, server_default=text("'[]'"))
    # e.g., ["decision_maker", "enterprise", "demo_requested"]

    # Status
    is_starred = Column(Boolean, nullable=False, server_default=text("false"))  # Important lead
    is_archived = Column(Boolean, nullable=False, server_default=text("false"))

    # Timestamps
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=text("NOW()"))
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=text("NOW()"))

    # Relationships
    sponsor = relationship("Sponsor", back_populates="leads")
