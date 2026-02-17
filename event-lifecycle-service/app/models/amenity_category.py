# app/models/amenity_category.py
import uuid
from sqlalchemy import Column, String, Integer, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.base_class import Base


class AmenityCategory(Base):
    __tablename__ = "amenity_categories"

    id = Column(
        String, primary_key=True, default=lambda: f"vac_{uuid.uuid4().hex[:12]}"
    )
    name = Column(String, nullable=False, unique=True)
    icon = Column(String, nullable=True)
    sort_order = Column(Integer, nullable=False, server_default="0")

    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    # Relationships
    amenities = relationship(
        "Amenity", back_populates="category", cascade="all, delete-orphan",
        order_by="Amenity.sort_order"
    )
