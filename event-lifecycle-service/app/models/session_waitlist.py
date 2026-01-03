# app/models/session_waitlist.py
import uuid
from sqlalchemy import Column, String, ForeignKey, DateTime, Integer, func, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from app.db.base_class import Base


class SessionWaitlist(Base):
    """
    Session Waitlist model for managing queue when sessions reach capacity.

    Features:
    - Priority tiers (VIP, PREMIUM, STANDARD)
    - Position tracking
    - Offer management with JWT tokens
    - Status tracking (WAITING, OFFERED, ACCEPTED, DECLINED, EXPIRED, LEFT)
    """
    __tablename__ = "session_waitlist"

    id = Column(String, primary_key=True, default=lambda: f"swl_{uuid.uuid4().hex[:12]}")
    session_id = Column(String, ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(String, nullable=False, index=True)  # No FK - users table in different database

    # Queue Management
    priority_tier = Column(String(20), nullable=False, server_default="STANDARD")  # STANDARD, VIP, PREMIUM
    position = Column(Integer, nullable=False)

    # Status
    status = Column(String(20), nullable=False, server_default="WAITING")  # WAITING, OFFERED, ACCEPTED, DECLINED, EXPIRED, LEFT

    # Offer Details
    offer_token = Column(String(512), nullable=True)  # JWT token for claiming spot
    offer_sent_at = Column(DateTime(timezone=True), nullable=True)
    offer_expires_at = Column(DateTime(timezone=True), nullable=True)
    offer_responded_at = Column(DateTime(timezone=True), nullable=True)

    # Timestamps
    joined_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    left_at = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        UniqueConstraint('session_id', 'user_id', name='unique_session_user'),
    )


class WaitlistEvent(Base):
    """
    Waitlist Events log for tracking all waitlist activities.

    Event types:
    - JOINED: User joined waitlist
    - POSITION_CHANGED: User's position in queue changed
    - OFFERED: User received spot offer
    - ACCEPTED: User accepted the offer
    - DECLINED: User declined the offer
    - EXPIRED: Offer expired
    - LEFT: User left waitlist voluntarily
    - REMOVED: User removed by admin
    """
    __tablename__ = "waitlist_events"

    id = Column(String, primary_key=True, default=lambda: f"wle_{uuid.uuid4().hex[:12]}")
    waitlist_entry_id = Column(String, ForeignKey("session_waitlist.id"), nullable=False, index=True)
    event_type = Column(String(50), nullable=False)  # JOINED, POSITION_CHANGED, OFFERED, ACCEPTED, etc.
    event_data = Column(JSONB, nullable=True, server_default=func.jsonb('{}'))  # Additional event data (renamed from 'metadata')
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
