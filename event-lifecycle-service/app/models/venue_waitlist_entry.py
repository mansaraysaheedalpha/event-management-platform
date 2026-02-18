# app/models/venue_waitlist_entry.py
import uuid
from sqlalchemy import (
    Column, String, Text, Boolean, Integer, DateTime, Date, ForeignKey,
    UniqueConstraint, Index, text, CheckConstraint
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.base_class import Base


class VenueWaitlistEntry(Base):
    __tablename__ = "venue_waitlist_entries"

    id = Column(
        String, primary_key=True, default=lambda: f"vwl_{uuid.uuid4().hex[:12]}"
    )
    organization_id = Column(String, nullable=False, index=True)
    venue_id = Column(
        String, ForeignKey("venues.id", ondelete="CASCADE"), nullable=False, index=True
    )
    source_rfp_id = Column(
        String, ForeignKey("rfps.id", ondelete="CASCADE"), nullable=False, index=True
    )
    source_rfp_venue_id = Column(
        String, ForeignKey("rfp_venues.id", ondelete="CASCADE"), nullable=False
    )

    # Context inherited from RFP (denormalized snapshot)
    desired_dates_start = Column(Date, nullable=True)
    desired_dates_end = Column(Date, nullable=True)
    dates_flexible = Column(Boolean, nullable=False)
    attendance_min = Column(Integer, nullable=False)
    attendance_max = Column(Integer, nullable=False)
    event_type = Column(String, nullable=False)
    space_requirements = Column(
        JSONB, nullable=False, server_default=text("'[]'::jsonb")
    )  # array of layout types

    # State
    status = Column(
        String, nullable=False, server_default=text("'waiting'")
    )  # waiting, offered, converted, expired, cancelled

    # Hold tracking
    hold_offered_at = Column(DateTime(timezone=True), nullable=True)
    hold_expires_at = Column(DateTime(timezone=True), nullable=True)
    hold_reminder_sent = Column(Boolean, nullable=False, server_default=text("false"))

    # Conversion
    converted_rfp_id = Column(
        String, ForeignKey("rfps.id", ondelete="SET NULL"), nullable=True
    )

    # Cancellation
    cancellation_reason = Column(
        String, nullable=True
    )  # no_longer_needed, found_alternative, declined_offer, nudge_declined, other
    cancellation_notes = Column(Text, nullable=True)

    # Expiry tracking
    expires_at = Column(
        DateTime(timezone=True), nullable=False
    )  # auto-calculated: 30 days after desired_dates_end, or 90 days after created_at
    still_interested_sent_at = Column(DateTime(timezone=True), nullable=True)
    still_interested_responded = Column(
        Boolean, nullable=False, server_default=text("false")
    )

    # NOTE: consecutive_no_responses is NOT a field — it is computed via get_consecutive_no_responses(venue_id)
    # NOTE: queue_position is NOT a field — it is computed dynamically via get_queue_position(entry)

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
    venue = relationship("Venue")
    source_rfp = relationship("RFP", foreign_keys=[source_rfp_id])
    source_rfp_venue = relationship("RFPVenue", foreign_keys=[source_rfp_venue_id])
    converted_rfp = relationship("RFP", foreign_keys=[converted_rfp_id])

    __table_args__ = (
        # Indexes for organizer's waitlist dashboard
        Index("ix_vwl_org_status", "organization_id", "status"),
        # Indexes for cascade queries (find next waiting entry)
        Index("ix_vwl_venue_status", "venue_id", "status"),
        # Partial index for expiry job
        Index(
            "ix_vwl_hold_expires",
            "hold_expires_at",
            postgresql_where=text("status = 'offered'"),
        ),
        # Partial index for auto-expiry job
        Index(
            "ix_vwl_expires_at",
            "expires_at",
            postgresql_where=text("status = 'waiting'"),
        ),
        # Partial unique constraint created in migration (ws001)
        # Prevents duplicate active entries for same org+venue
    )
