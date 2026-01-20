# app/models/expo_booth.py
"""
ExpoBooth model - represents a sponsor's virtual booth in the expo hall.

Each booth belongs to a sponsor and contains their branding, resources,
and configuration for attendee interactions (chat, video calls, etc.).
This model is used for initial booth setup and configuration, while
real-time interactions are handled by the real-time-service.
"""

import uuid
from sqlalchemy import Column, String, Integer, Boolean, DateTime, Text, Enum, ForeignKey, JSON, text
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import relationship
from app.db.base_class import Base
import enum


class BoothTier(str, enum.Enum):
    """Booth tier levels - affects display priority and features."""
    PLATINUM = "PLATINUM"
    GOLD = "GOLD"
    SILVER = "SILVER"
    BRONZE = "BRONZE"
    STARTUP = "STARTUP"


class ExpoBooth(Base):
    __tablename__ = "expo_booths"

    id = Column(
        String, primary_key=True, default=lambda: f"booth_{uuid.uuid4().hex[:12]}"
    )
    organization_id = Column(String, nullable=False, index=True)
    expo_hall_id = Column(String, ForeignKey("expo_halls.id"), nullable=False, index=True)
    sponsor_id = Column(String, ForeignKey("sponsors.id"), nullable=False, index=True)

    # Booth Identity
    booth_number = Column(String(20), nullable=False)
    tier = Column(
        Enum(BoothTier, name="booth_tier"),
        nullable=False,
        server_default=text("'BRONZE'")
    )
    name = Column(String(200), nullable=False)
    tagline = Column(String(300), nullable=True)
    description = Column(Text, nullable=True)

    # Media Assets
    logo_url = Column(String(500), nullable=True)
    banner_url = Column(String(500), nullable=True)
    video_url = Column(String(500), nullable=True)  # Booth video loop

    # Resources (JSON array)
    # Format: [{ "id": "...", "title": "...", "type": "pdf|doc|video|link",
    #            "url": "...", "description": "..." }]
    resources = Column(JSON, nullable=False, server_default=text("'[]'"))

    # Call-to-action buttons (JSON array)
    # Format: [{ "id": "...", "label": "...", "url": "...", "style": "primary|secondary",
    #            "icon": "..." }]
    cta_buttons = Column(JSON, nullable=False, server_default=text("'[]'"))

    # Staff Management - user IDs who can manage this booth
    staff_ids = Column(ARRAY(String), nullable=False, server_default=text("'{}'"))

    # Features
    chat_enabled = Column(Boolean, nullable=False, server_default=text("true"))
    video_enabled = Column(Boolean, nullable=False, server_default=text("true"))

    # Floor plan positioning (for FLOOR_PLAN layout)
    position_x = Column(Integer, nullable=True)
    position_y = Column(Integer, nullable=True)
    width = Column(Integer, nullable=True)
    height = Column(Integer, nullable=True)

    # Category for filtering
    category = Column(String(100), nullable=True, index=True)

    # Sorting within tier
    display_order = Column(Integer, nullable=False, server_default=text("0"))

    # Status
    is_active = Column(Boolean, nullable=False, server_default=text("true"))

    # Timestamps
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=text("NOW()"))
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=text("NOW()"))

    # Relationships
    expo_hall = relationship("ExpoHall", back_populates="booths")
    sponsor = relationship("Sponsor", back_populates="expo_booth")

    # Unique constraint: booth number must be unique within expo hall
    __table_args__ = (
        {"extend_existing": True},
    )
