# app/models/venue_space.py
import uuid
from sqlalchemy import (
    Column, String, Text, Integer, DateTime, ForeignKey, ARRAY
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.base_class import Base


class VenueSpace(Base):
    __tablename__ = "venue_spaces"

    id = Column(
        String, primary_key=True, default=lambda: f"vsp_{uuid.uuid4().hex[:12]}"
    )
    venue_id = Column(
        String, ForeignKey("venues.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    capacity = Column(Integer, nullable=True)
    floor_level = Column(String, nullable=True)
    layout_options = Column(ARRAY(String), nullable=False, server_default="{}")
    sort_order = Column(Integer, nullable=False, server_default="0")

    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    # Relationships
    venue = relationship("Venue", back_populates="spaces")
    pricing = relationship(
        "VenueSpacePricing", back_populates="space", cascade="all, delete-orphan"
    )
    photos = relationship(
        "VenuePhoto",
        primaryjoin="VenueSpace.id == foreign(VenuePhoto.space_id)",
        viewonly=True,
    )
