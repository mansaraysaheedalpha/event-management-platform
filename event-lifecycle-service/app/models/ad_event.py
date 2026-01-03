# app/models/ad_event.py
import uuid
from sqlalchemy import Column, String, Integer, DateTime, Text, ForeignKey, text
from sqlalchemy.dialects.postgresql import INET
from app.db.base_class import Base


class AdEvent(Base):
    __tablename__ = "ad_events"

    id = Column(String, primary_key=True, default=lambda: f"adev_{uuid.uuid4().hex[:12]}")
    ad_id = Column(String, ForeignKey("ads.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(String, nullable=True)  # No FK - users table is in different database (postgres-user-org)
    session_token = Column(String(255), nullable=True)

    # Event classification
    event_type = Column(String(20), nullable=False)  # IMPRESSION, CLICK
    context = Column(String(255), nullable=True)  # Page URL or session ID where ad was shown

    # Viewability metrics (for impressions)
    viewable_duration_ms = Column(Integer, nullable=True)
    viewport_percentage = Column(Integer, nullable=True)

    # Technical data
    user_agent = Column(Text, nullable=True)
    ip_address = Column(INET, nullable=True)
    referer = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), nullable=False, server_default=text("NOW()"))
