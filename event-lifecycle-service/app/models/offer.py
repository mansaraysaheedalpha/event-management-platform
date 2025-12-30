# app/models/offer.py
import uuid
from sqlalchemy import Column, String, text, ForeignKey, Float, DateTime, Boolean, Integer, JSON
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import relationship
from app.db.base_class import Base


class Offer(Base):
    __tablename__ = "offers"

    id = Column(
        String, primary_key=True, default=lambda: f"offer_{uuid.uuid4().hex[:12]}"
    )
    organization_id = Column(String, nullable=False, index=True)
    event_id = Column(String, ForeignKey("events.id"), nullable=False, index=True)

    # Basic Info
    title = Column(String, nullable=False)
    description = Column(String, nullable=True)
    offer_type = Column(String, nullable=False)  # TICKET_UPGRADE, MERCHANDISE, EXCLUSIVE_CONTENT, SERVICE

    # Pricing
    price = Column(Float, nullable=False)
    original_price = Column(Float, nullable=True)
    currency = Column(String, nullable=False, default="USD")

    # Media
    image_url = Column(String, nullable=True)

    # Inventory Management
    inventory_total = Column(Integer, nullable=True)  # NULL = unlimited
    inventory_sold = Column(Integer, nullable=False, server_default=text("0"))
    inventory_reserved = Column(Integer, nullable=False, server_default=text("0"))

    # Stripe Integration
    stripe_product_id = Column(String(255), nullable=True, unique=True)
    stripe_price_id = Column(String(255), nullable=True, unique=True)

    # Targeting & Placement
    placement = Column(String(50), nullable=False, server_default=text("'IN_EVENT'"))  # CHECKOUT, POST_PURCHASE, IN_EVENT, EMAIL
    target_sessions = Column(ARRAY(String), nullable=True, server_default=text("'{}'"))
    target_ticket_tiers = Column(ARRAY(String), nullable=True, server_default=text("'{}'"))

    # Scheduling
    starts_at = Column(DateTime(timezone=True), nullable=True, server_default=text("NOW()"))
    expires_at = Column(DateTime(timezone=True), nullable=True)

    # Status
    is_active = Column(Boolean, nullable=False, server_default=text("true"))
    is_archived = Column(Boolean, nullable=False, server_default=text("false"))

    # Metadata (renamed from 'metadata' to avoid SQLAlchemy reserved name)
    offer_metadata = Column("metadata", JSON, nullable=True, server_default=text("'{}'"))

    # Timestamps
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=text("NOW()"))
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=text("NOW()"), onupdate=text("NOW()"))

    # Relationships
    purchases = relationship("OfferPurchase", back_populates="offer", cascade="all, delete-orphan")

    @property
    def inventory_available(self) -> int:
        """Calculate available inventory."""
        if self.inventory_total is None:
            return 9999999  # Unlimited
        return self.inventory_total - (self.inventory_sold + self.inventory_reserved)

    @property
    def is_available(self) -> bool:
        """Check if offer is currently available."""
        from datetime import datetime, timezone

        if self.is_archived or not self.is_active:
            return False

        now = datetime.now(timezone.utc)

        if self.starts_at and now < self.starts_at:
            return False

        if self.expires_at and now > self.expires_at:
            return False

        if self.inventory_available <= 0:
            return False

        return True
