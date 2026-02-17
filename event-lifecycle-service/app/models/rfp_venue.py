# app/models/rfp_venue.py
import uuid
from sqlalchemy import (
    Column, String, Float, DateTime, ForeignKey, UniqueConstraint, Index
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.base_class import Base


class RFPVenue(Base):
    __tablename__ = "rfp_venues"

    id = Column(
        String, primary_key=True, default=lambda: f"rfv_{uuid.uuid4().hex[:12]}"
    )
    rfp_id = Column(
        String, ForeignKey("rfps.id", ondelete="CASCADE"), nullable=False, index=True
    )
    venue_id = Column(
        String, ForeignKey("venues.id", ondelete="CASCADE"), nullable=False, index=True
    )
    status = Column(String, nullable=False, server_default="received")

    # Tracking timestamps
    notified_at = Column(DateTime(timezone=True), nullable=True)
    viewed_at = Column(DateTime(timezone=True), nullable=True)
    responded_at = Column(DateTime(timezone=True), nullable=True)

    # Pre-computed fit indicators (snapshotted at send time)
    capacity_fit = Column(String, nullable=True)  # good_fit, tight_fit, oversized, poor_fit
    amenity_match_pct = Column(Float, nullable=True)  # 0-100

    # Timestamps
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
    rfp = relationship("RFP", back_populates="venues")
    venue = relationship("Venue")
    response = relationship(
        "VenueResponse", back_populates="rfp_venue", uselist=False,
        cascade="all, delete-orphan"
    )
    negotiation_messages = relationship(
        "NegotiationMessage", back_populates="rfp_venue", cascade="all, delete-orphan"
    )

    __table_args__ = (
        UniqueConstraint("rfp_id", "venue_id", name="uq_rfp_venue"),
    )
