# app/models/ticket_type.py
from sqlalchemy import Column, String, Boolean, DateTime, Integer, Text, ForeignKey, text
from sqlalchemy.orm import relationship
from app.db.base_class import Base
import uuid
from datetime import datetime, timezone as tz


class TicketType(Base):
    __tablename__ = "ticket_types"

    id = Column(
        String, primary_key=True, default=lambda: f"tt_{uuid.uuid4().hex[:12]}"
    )
    event_id = Column(String, ForeignKey("events.id", ondelete="CASCADE"), nullable=False, index=True)
    organization_id = Column(String, nullable=False, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    price = Column(Integer, nullable=False, server_default="0")  # Price in cents
    currency = Column(String(3), nullable=False, server_default="USD")
    quantity_total = Column(Integer, nullable=True)  # NULL = unlimited
    quantity_sold = Column(Integer, server_default="0", nullable=False)
    quantity_reserved = Column(Integer, server_default="0", nullable=False)  # Held in pending orders
    min_per_order = Column(Integer, server_default="1", nullable=False)
    max_per_order = Column(Integer, server_default="10", nullable=False)
    sales_start_at = Column(DateTime(timezone=True), nullable=True)
    sales_end_at = Column(DateTime(timezone=True), nullable=True)
    is_active = Column(Boolean, server_default=text("true"), nullable=False)
    is_hidden = Column(Boolean, server_default=text("false"), nullable=False)  # Hidden but accessible via direct link
    sort_order = Column(Integer, server_default="0", nullable=False)
    is_archived = Column(Boolean, server_default=text("false"), nullable=False)
    created_by = Column(String, nullable=True)  # User ID who created
    created_at = Column(DateTime(timezone=True), server_default=text("now()"), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=text("now()"), nullable=False)

    # Relationships
    event = relationship("Event", foreign_keys=[event_id])
    order_items = relationship("OrderItem", back_populates="ticket_type")
    tickets = relationship("Ticket", back_populates="ticket_type")

    @property
    def quantity_available(self):
        """Calculate available quantity for this ticket type."""
        if self.quantity_total is None:
            return None  # Unlimited
        return max(0, self.quantity_total - self.quantity_sold - self.quantity_reserved)

    @property
    def is_sold_out(self):
        """Check if ticket type is sold out."""
        if self.quantity_total is None:
            return False
        return (self.quantity_sold + self.quantity_reserved) >= self.quantity_total

    @property
    def is_on_sale(self) -> bool:
        """Check if ticket type is currently on sale."""
        if not self.is_active:
            return False

        now = datetime.now(tz.utc)

        # Check sales window
        if self.sales_start_at and now < self.sales_start_at:
            return False  # Sales haven't started

        if self.sales_end_at and now > self.sales_end_at:
            return False  # Sales have ended

        # Check inventory
        if self.quantity_total is not None:
            available = self.quantity_total - self.quantity_sold - self.quantity_reserved
            if available <= 0:
                return False  # Sold out

        return True

    @property
    def revenue(self) -> int:
        """Calculate total revenue from this ticket type."""
        return self.price * self.quantity_sold
