# app/models/expo_hall.py
"""
ExpoHall model - represents a virtual expo hall for an event.

The expo hall is a virtual space where sponsors can set up booths
to showcase their products/services, interact with attendees, and
capture leads. This model handles the configuration of the expo hall
itself, while individual booths are managed in expo_booth.py.
"""

import uuid
from sqlalchemy import Column, String, Boolean, DateTime, Text, Enum, ForeignKey, text
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import relationship
from app.db.base_class import Base
import enum


class ExpoHallLayout(str, enum.Enum):
    """Layout options for the expo hall display."""
    GRID = "GRID"           # Traditional grid layout of booth cards
    FLOOR_PLAN = "FLOOR_PLAN"  # Visual floor plan with positioned booths
    LIST = "LIST"           # List view with detailed booth info


class ExpoHall(Base):
    __tablename__ = "expo_halls"

    id = Column(
        String, primary_key=True, default=lambda: f"expo_{uuid.uuid4().hex[:12]}"
    )
    organization_id = Column(String, nullable=False, index=True)
    event_id = Column(String, ForeignKey("events.id"), nullable=False, unique=True, index=True)

    # Hall Details
    name = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    layout = Column(
        Enum(ExpoHallLayout, name="expo_hall_layout"),
        nullable=False,
        server_default=text("'GRID'")
    )

    # Categories for filtering booths
    categories = Column(ARRAY(String), nullable=False, server_default=text("'{}'"))

    # Availability window
    opens_at = Column(DateTime(timezone=True), nullable=True)
    closes_at = Column(DateTime(timezone=True), nullable=True)

    # Customization
    banner_url = Column(String(500), nullable=True)
    welcome_message = Column(Text, nullable=True)

    # Status
    is_active = Column(Boolean, nullable=False, server_default=text("true"))

    # Timestamps
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=text("NOW()"))
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=text("NOW()"))

    # Relationships
    booths = relationship("ExpoBooth", back_populates="expo_hall", cascade="all, delete-orphan")
