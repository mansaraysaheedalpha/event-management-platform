# app/models/venue_photo.py
import uuid
from sqlalchemy import Column, String, Text, Integer, Boolean, DateTime, ForeignKey, text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.base_class import Base


class VenuePhoto(Base):
    __tablename__ = "venue_photos"

    id = Column(
        String, primary_key=True, default=lambda: f"vph_{uuid.uuid4().hex[:12]}"
    )
    venue_id = Column(
        String, ForeignKey("venues.id", ondelete="CASCADE"), nullable=False, index=True
    )
    space_id = Column(
        String, ForeignKey("venue_spaces.id", ondelete="SET NULL"), nullable=True
    )
    url = Column(String, nullable=False)
    s3_key = Column(String, nullable=False)
    category = Column(String, nullable=True)  # exterior|interior|rooms|amenities|catering|general
    caption = Column(Text, nullable=True)
    sort_order = Column(Integer, nullable=False, server_default="0")
    is_cover = Column(Boolean, nullable=False, server_default=text("false"))

    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    # Relationships
    venue = relationship("Venue", back_populates="photos", foreign_keys=[venue_id])
