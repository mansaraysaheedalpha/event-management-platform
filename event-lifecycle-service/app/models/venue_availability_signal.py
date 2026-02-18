# app/models/venue_availability_signal.py
import uuid
from sqlalchemy import (
    Column, String, DateTime, Date, ForeignKey, Index
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func
from app.db.base_class import Base


class VenueAvailabilitySignal(Base):
    """
    Append-only audit log of availability signals for a venue.
    Never updated or deleted. Used by the inference engine.
    """

    __tablename__ = "venue_availability_signals"

    id = Column(
        String, primary_key=True, default=lambda: f"vas_{uuid.uuid4().hex[:12]}"
    )
    venue_id = Column(
        String, ForeignKey("venues.id", ondelete="CASCADE"), nullable=False, index=True
    )
    signal_type = Column(
        String, nullable=False
    )  # confirmed, tentative, unavailable, no_response, awarded, lost_to_competitor,
    # rfp_cancelled, manual_available, manual_unavailable

    # Source tracking (null for manual signals)
    source_rfp_id = Column(
        String, ForeignKey("rfps.id", ondelete="SET NULL"), nullable=True
    )
    source_rfp_venue_id = Column(
        String, ForeignKey("rfp_venues.id", ondelete="SET NULL"), nullable=True
    )

    # The date this signal applies to (from RFP preferred dates)
    signal_date = Column(Date, nullable=True)

    # When the signal was recorded
    recorded_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    # Additional context (attendance size, event type, etc.)
    signal_metadata = Column(JSONB, nullable=True)

    # NO relationships back to other models — this is an append-only audit log

    __table_args__ = (
        # For inference queries (last 90 days)
        Index("ix_vas_venue_recorded", "venue_id", "recorded_at"),
        # For signal counting
        Index("ix_vas_venue_signal_type", "venue_id", "signal_type"),
    )
