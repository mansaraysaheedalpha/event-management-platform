# app/models/amenity.py
import uuid
from sqlalchemy import Column, String, Text, Integer, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.base_class import Base


class Amenity(Base):
    __tablename__ = "amenities"

    id = Column(
        String, primary_key=True, default=lambda: f"vam_{uuid.uuid4().hex[:12]}"
    )
    category_id = Column(
        String,
        ForeignKey("amenity_categories.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    icon = Column(String, nullable=True)
    metadata_schema = Column(JSONB, nullable=True)
    sort_order = Column(Integer, nullable=False, server_default="0")

    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    # Relationships
    category = relationship("AmenityCategory", back_populates="amenities")
