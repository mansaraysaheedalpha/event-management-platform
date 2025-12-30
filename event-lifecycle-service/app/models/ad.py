# app/models/ad.py
import uuid
from sqlalchemy import Column, String, Integer, Boolean, DateTime, JSON, ForeignKey, text
from sqlalchemy.dialects.postgresql import ARRAY
from app.db.base_class import Base


class Ad(Base):
    __tablename__ = "ads"

    id = Column(String, primary_key=True, default=lambda: f"ad_{uuid.uuid4().hex[:12]}")
    organization_id = Column(String, nullable=False, index=True)
    event_id = Column(String, ForeignKey("events.id"), nullable=True, index=True)

    # Ad Details
    name = Column(String, nullable=False)  # Internal name for organizers
    content_type = Column(String, nullable=False)  # BANNER, VIDEO, SPONSORED_SESSION, INTERSTITIAL
    media_url = Column(String, nullable=False)
    click_url = Column(String, nullable=False)

    # Display Settings
    display_duration_seconds = Column(Integer, nullable=False, server_default=text("30"))
    aspect_ratio = Column(String(20), nullable=False, server_default=text("'16:9'"))

    # Scheduling
    starts_at = Column(DateTime(timezone=True), nullable=False, server_default=text("NOW()"))
    ends_at = Column(DateTime(timezone=True), nullable=True)

    # Targeting
    placements = Column(ARRAY(String(50)), nullable=False, server_default=text("'{EVENT_HERO}'"))
    target_sessions = Column(ARRAY(String), nullable=True, server_default=text("'{}'"))

    # Rotation & Frequency
    weight = Column(Integer, nullable=False, server_default=text("1"))  # Higher weight = shown more
    frequency_cap = Column(Integer, nullable=False, server_default=text("3"))  # Max impressions per user per session

    # Status
    is_active = Column(Boolean, nullable=False, server_default=text("true"))
    is_archived = Column(Boolean, nullable=False, server_default=text("false"))

    # Custom Metadata
    custom_metadata = Column("metadata", JSON, nullable=True, server_default=text("'{}'"))

    # Timestamps
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=text("NOW()"))
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=text("NOW()"))
