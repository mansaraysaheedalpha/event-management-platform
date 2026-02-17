# app/models/venue_space_pricing.py
import uuid
from sqlalchemy import Column, String, Numeric, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.base_class import Base


class VenueSpacePricing(Base):
    __tablename__ = "venue_space_pricing"

    id = Column(
        String, primary_key=True, default=lambda: f"vpr_{uuid.uuid4().hex[:12]}"
    )
    space_id = Column(
        String,
        ForeignKey("venue_spaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    rate_type = Column(String, nullable=False)  # "hourly" | "half_day" | "full_day"
    amount = Column(Numeric(12, 2), nullable=False)
    currency = Column(String(3), nullable=False)  # ISO 4217

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
    space = relationship("VenueSpace", back_populates="pricing")
