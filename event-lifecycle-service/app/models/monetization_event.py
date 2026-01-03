# app/models/monetization_event.py
import uuid
from sqlalchemy import Column, String, Integer, DateTime, Text, JSON, CheckConstraint, text
from sqlalchemy.dialects.postgresql import INET, UUID as PGUUID
from app.db.base_class import Base


class MonetizationEvent(Base):
    """
    Unified table for tracking all monetization events across:
    - Offers (views, clicks, add-to-cart, purchases, refunds)
    - Ads (impressions, viewable impressions, clicks)
    - Waitlist (joins, offers sent/accepted/declined/expired)

    Used for:
    - Conversion funnel analysis
    - Revenue attribution
    - Comprehensive analytics dashboard
    - Performance tracking
    """
    __tablename__ = "monetization_events"

    id = Column(PGUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    event_id = Column(String, nullable=False, index=True)  # Event/session ID
    user_id = Column(String, nullable=True, index=True)  # Nullable for anonymous users
    session_token = Column(String(255), nullable=True)  # Browser session for anonymous tracking

    # Event Classification
    event_type = Column(
        String(50),
        nullable=False,
        index=True
    )
    entity_type = Column(
        String(20),
        nullable=False,
        index=True
    )
    entity_id = Column(String, nullable=False, index=True)  # Offer ID, Ad ID, or Waitlist ID

    # Revenue Attribution
    revenue_cents = Column(Integer, nullable=False, server_default=text("0"))
    currency = Column(String(3), nullable=False, server_default=text("'USD'"))

    # Context (flexible JSON for additional data)
    context = Column(JSON, nullable=False, server_default=text("'{}'::jsonb"))

    # Technical Data
    user_agent = Column(Text, nullable=True)
    ip_address = Column(INET, nullable=True)

    # Timestamp
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=text("NOW()"), index=True)

    # Constraints
    __table_args__ = (
        CheckConstraint(
            "event_type IN ("
            "'OFFER_VIEW', 'OFFER_CLICK', 'OFFER_ADD_TO_CART', 'OFFER_PURCHASE', 'OFFER_REFUND', "
            "'AD_IMPRESSION', 'AD_VIEWABLE_IMPRESSION', 'AD_CLICK', "
            "'WAITLIST_JOIN', 'WAITLIST_OFFER_SENT', 'WAITLIST_OFFER_ACCEPTED', "
            "'WAITLIST_OFFER_DECLINED', 'WAITLIST_OFFER_EXPIRED'"
            ")",
            name="valid_event_type"
        ),
        CheckConstraint(
            "entity_type IN ('OFFER', 'AD', 'WAITLIST')",
            name="valid_entity_type"
        ),
    )
