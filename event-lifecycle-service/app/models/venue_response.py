# app/models/venue_response.py
import uuid
from sqlalchemy import (
    Column, String, Text, Integer, DateTime, Numeric, ForeignKey, Date
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.base_class import Base


class VenueResponse(Base):
    __tablename__ = "venue_responses"

    id = Column(
        String, primary_key=True, default=lambda: f"vrs_{uuid.uuid4().hex[:12]}"
    )
    rfp_venue_id = Column(
        String,
        ForeignKey("rfp_venues.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )

    availability = Column(String, nullable=False)  # confirmed, tentative, unavailable
    proposed_space_id = Column(String, nullable=True)  # reference to VenueSpace
    proposed_space_name = Column(String, nullable=False)  # denormalized snapshot
    proposed_space_capacity = Column(Integer, nullable=True)  # denormalized snapshot

    # Pricing — all in venue's chosen currency
    currency = Column(String(3), nullable=False)
    space_rental_price = Column(Numeric(14, 2), nullable=True)
    catering_price_per_head = Column(Numeric(14, 2), nullable=True)
    av_equipment_fees = Column(Numeric(14, 2), nullable=True)
    setup_cleanup_fees = Column(Numeric(14, 2), nullable=True)
    other_fees = Column(Numeric(14, 2), nullable=True)
    other_fees_description = Column(String, nullable=True)

    # Amenity details
    included_amenity_ids = Column(JSONB, nullable=False, server_default="'[]'::jsonb")
    extra_cost_amenities = Column(JSONB, nullable=False, server_default="'[]'::jsonb")

    # Terms
    cancellation_policy = Column(Text, nullable=True)
    deposit_amount = Column(Numeric(14, 2), nullable=True)
    payment_schedule = Column(Text, nullable=True)
    alternative_dates = Column(JSONB, nullable=True)
    quote_valid_until = Column(Date, nullable=True)
    notes = Column(Text, nullable=True)

    # Calculated
    total_estimated_cost = Column(Numeric(14, 2), nullable=False)

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
    rfp_venue = relationship("RFPVenue", back_populates="response")
