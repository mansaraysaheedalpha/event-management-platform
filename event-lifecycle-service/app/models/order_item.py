# app/models/order_item.py
from sqlalchemy import Column, String, DateTime, Integer, Text, ForeignKey, CheckConstraint, text
from sqlalchemy.orm import relationship
from app.db.base_class import Base
import uuid


class OrderItem(Base):
    __tablename__ = "order_items"

    id = Column(
        String, primary_key=True, default=lambda: f"oi_{uuid.uuid4().hex[:12]}"
    )
    order_id = Column(String, ForeignKey("orders.id", ondelete="CASCADE"), nullable=False, index=True)
    ticket_type_id = Column(String, ForeignKey("ticket_types.id"), nullable=False, index=True)
    quantity = Column(Integer, nullable=False)
    unit_price = Column(Integer, nullable=False)  # Price per ticket in cents
    total_price = Column(Integer, nullable=False)  # quantity * unit_price

    # Snapshot of ticket type at purchase time
    ticket_type_name = Column(String(255), nullable=False)
    ticket_type_description = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=text("now()"), nullable=False)

    # Table constraints
    __table_args__ = (
        CheckConstraint("quantity > 0", name="check_order_items_quantity_positive"),
    )

    # Relationships
    order = relationship("Order", back_populates="items")
    ticket_type = relationship("TicketType", foreign_keys=[ticket_type_id])
