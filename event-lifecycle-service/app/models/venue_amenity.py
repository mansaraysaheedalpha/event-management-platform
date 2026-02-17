# app/models/venue_amenity.py
from sqlalchemy import Column, String, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.base_class import Base


class VenueAmenity(Base):
    __tablename__ = "venue_amenities"

    venue_id = Column(
        String,
        ForeignKey("venues.id", ondelete="CASCADE"),
        primary_key=True,
    )
    amenity_id = Column(
        String,
        ForeignKey("amenities.id", ondelete="CASCADE"),
        primary_key=True,
    )
    extra_metadata = Column("metadata", JSONB, nullable=True)

    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    # Relationships
    venue = relationship("Venue", back_populates="venue_amenities")
    amenity = relationship("Amenity")
