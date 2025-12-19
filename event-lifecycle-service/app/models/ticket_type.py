# app/models/ticket_type.py
from sqlalchemy import Column, String, Boolean, DateTime, Integer, Text, ForeignKey, text
from sqlalchemy.orm import relationship
from app.db.base_class import Base
import uuid


class TicketType(Base):
    __tablename__ = "ticket_types"

    id = Column(
        String, primary_key=True, default=lambda: f"tt_{uuid.uuid4().hex[:12]}"
    )
    event_id = Column(String, ForeignKey("events.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    price = Column(Integer, nullable=False, server_default="0")  # Price in cents
    currency = Column(String(3), nullable=False, server_default="USD")
    quantity_total = Column(Integer, nullable=True)  # NULL = unlimited
    quantity_sold = Column(Integer, server_default="0", nullable=False)
    min_per_order = Column(Integer, server_default="1", nullable=False)
    max_per_order = Column(Integer, server_default="10", nullable=False)
    sales_start_at = Column(DateTime(timezone=True), nullable=True)
    sales_end_at = Column(DateTime(timezone=True), nullable=True)
    is_active = Column(Boolean, server_default=text("true"), nullable=False)
    sort_order = Column(Integer, server_default="0", nullable=False)
    is_archived = Column(Boolean, server_default=text("false"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=text("now()"), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=text("now()"), nullable=False)

    # Relationships
    event = relationship("Event", foreign_keys=[event_id])

    @property
    def quantity_available(self):
        """Calculate available quantity for this ticket type."""
        if self.quantity_total is None:
            return None  # Unlimited
        return max(0, self.quantity_total - self.quantity_sold)

    @property
    def is_sold_out(self):
        """Check if ticket type is sold out."""
        if self.quantity_total is None:
            return False
        return self.quantity_sold >= self.quantity_total
