# app/models/rfp.py
import uuid
from sqlalchemy import (
    Column, String, Text, Boolean, Integer, Float, DateTime, Date,
    Numeric, Index, text
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.base_class import Base


class RFP(Base):
    __tablename__ = "rfps"

    id = Column(
        String, primary_key=True, default=lambda: f"rfp_{uuid.uuid4().hex[:12]}"
    )
    organization_id = Column(String, nullable=False, index=True)
    title = Column(String, nullable=False)
    event_type = Column(String, nullable=False)  # conference, wedding, etc.
    attendance_min = Column(Integer, nullable=False)
    attendance_max = Column(Integer, nullable=False)
    preferred_dates_start = Column(Date, nullable=True)
    preferred_dates_end = Column(Date, nullable=True)
    dates_flexible = Column(Boolean, nullable=False, server_default=text("false"))
    duration = Column(String, nullable=False)
    space_requirements = Column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))
    required_amenity_ids = Column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))
    catering_needs = Column(String, nullable=False)  # none, in_house_preferred, etc.
    budget_min = Column(Numeric(14, 2), nullable=True)
    budget_max = Column(Numeric(14, 2), nullable=True)
    budget_currency = Column(String(3), nullable=True)
    preferred_currency = Column(String(3), nullable=False, server_default=text("'USD'"))
    additional_notes = Column(Text, nullable=True)
    response_deadline = Column(DateTime(timezone=True), nullable=False)
    linked_event_id = Column(String, nullable=True)  # optional FK to events

    # Status
    status = Column(String, nullable=False, server_default=text("'draft'"))
    sent_at = Column(DateTime(timezone=True), nullable=True)

    # Organizer contact (for email notifications)
    organizer_email = Column(String, nullable=True)

    # Idempotency tracking (prevent duplicate notifications)
    deadline_processed_at = Column(DateTime(timezone=True), nullable=True)

    # Template fields (schema-ready, no UI)
    is_template = Column(Boolean, nullable=False, server_default=text("false"))
    template_name = Column(String, nullable=True)

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
    venues = relationship(
        "RFPVenue", back_populates="rfp", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_rfps_org_status", "organization_id", "status"),
    )
