# app/models/promo_code_usage.py
from sqlalchemy import Column, String, DateTime, Integer, ForeignKey, text
from sqlalchemy.orm import relationship
from app.db.base_class import Base
import uuid


class PromoCodeUsage(Base):
    """Tracks promo code usage per user/order."""
    __tablename__ = "promo_code_usages"

    id = Column(
        String, primary_key=True, default=lambda: f"pcu_{uuid.uuid4().hex[:12]}"
    )
    promo_code_id = Column(
        String,
        ForeignKey("promo_codes.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    order_id = Column(
        String,
        ForeignKey("orders.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    user_id = Column(String, nullable=True, index=True)
    guest_email = Column(String(255), nullable=True)
    discount_applied = Column(Integer, nullable=False)  # Actual discount amount in cents
    used_at = Column(DateTime(timezone=True), server_default=text("now()"), nullable=False)

    # Relationships
    promo_code = relationship("PromoCode", back_populates="usages")
    order = relationship("Order", foreign_keys=[order_id])

    @property
    def user_identifier(self) -> str:
        """Get the user identifier (user_id or guest_email)."""
        return self.user_id or self.guest_email or ""
