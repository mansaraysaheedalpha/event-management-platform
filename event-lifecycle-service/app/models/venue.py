# app/models/venue.py
import uuid
from sqlalchemy import (
    Column, String, Text, Boolean, Float, Integer, DateTime, text, Index
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.base_class import Base


class Venue(Base):
    __tablename__ = "venues"

    id = Column(
        String, primary_key=True, default=lambda: f"ven_{uuid.uuid4().hex[:12]}"
    )
    organization_id = Column(String, nullable=False, index=True)
    name = Column(String, nullable=False)
    address = Column(String, nullable=True)

    # --- NEW FIELDS ---
    slug = Column(String, unique=True, index=True, nullable=True)
    description = Column(Text, nullable=True)
    city = Column(String, nullable=True, index=True)
    country = Column(String(2), nullable=True, index=True)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    website = Column(String, nullable=True)
    phone = Column(String, nullable=True)
    email = Column(String, nullable=True)
    whatsapp = Column(String, nullable=True)

    cover_photo_id = Column(String, nullable=True)
    total_capacity = Column(Integer, nullable=True)

    # Directory fields
    is_public = Column(Boolean, nullable=False, server_default=text("false"))
    status = Column(String, nullable=False, server_default=text("'draft'"))
    rejection_reason = Column(Text, nullable=True)
    submitted_at = Column(DateTime(timezone=True), nullable=True)
    approved_at = Column(DateTime(timezone=True), nullable=True)
    verified = Column(Boolean, nullable=False, server_default=text("false"))
    domain_match = Column(Boolean, nullable=False, server_default=text("false"))

    is_archived = Column(Boolean, nullable=False, server_default=text("false"))
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
    spaces = relationship(
        "VenueSpace", back_populates="venue", cascade="all, delete-orphan",
        order_by="VenueSpace.sort_order"
    )
    photos = relationship(
        "VenuePhoto", back_populates="venue", cascade="all, delete-orphan",
        foreign_keys="VenuePhoto.venue_id",
        order_by="VenuePhoto.sort_order"
    )
    venue_amenities = relationship(
        "VenueAmenity", back_populates="venue", cascade="all, delete-orphan"
    )
    verification_documents = relationship(
        "VenueVerificationDocument", back_populates="venue", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_venues_status", "status"),
        Index("ix_venues_lat_lng", "latitude", "longitude"),
    )
