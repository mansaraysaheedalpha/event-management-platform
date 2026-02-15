# app/models/ticket.py
from sqlalchemy import Column, String, DateTime, ForeignKey, Text, text
from sqlalchemy.orm import relationship
from app.db.base_class import Base
import uuid
import secrets


class Ticket(Base):
    """Stores actual tickets issued to attendees after successful purchase."""
    __tablename__ = "tickets"

    id = Column(
        String, primary_key=True, default=lambda: f"tkt_{uuid.uuid4().hex[:12]}"
    )

    # Relationships to orders
    order_id = Column(
        String,
        ForeignKey("orders.id"),
        nullable=False,
        index=True
    )
    order_item_id = Column(
        String,
        ForeignKey("order_items.id"),
        nullable=False
    )
    ticket_type_id = Column(
        String,
        ForeignKey("ticket_types.id"),
        nullable=False,
        index=True
    )
    event_id = Column(
        String,
        ForeignKey("events.id"),
        nullable=False,
        index=True
    )

    # Owner information
    user_id = Column(String, nullable=True, index=True)
    attendee_email = Column(String(255), nullable=False)
    attendee_name = Column(String(255), nullable=False)

    # Ticket identification (unique, scannable)
    ticket_code = Column(String(20), unique=True, nullable=False)  # Format: TKT-XXXXXX-XX
    qr_code_data = Column(Text, nullable=True)  # Encoded QR data

    # Status: 'valid', 'checked_in', 'cancelled', 'transferred', 'refunded'
    status = Column(String(50), server_default="valid", nullable=False)

    # Check-in information
    checked_in_at = Column(DateTime(timezone=True), nullable=True)
    checked_in_by = Column(String, nullable=True)  # Staff user ID who checked in
    check_in_location = Column(String(255), nullable=True)  # Entry point name

    # Transfer information (if transferred to another person)
    transferred_from_ticket_id = Column(
        String,
        ForeignKey("tickets.id"),
        nullable=True
    )
    transferred_at = Column(DateTime(timezone=True), nullable=True)

    # Expiration (for future server-side expiration enforcement)
    expires_at = Column(DateTime(timezone=True), nullable=True)

    # SMS check-in PIN (6-digit numeric, unique per event, for feature-phone users)
    check_in_pin = Column(String(6), nullable=True, index=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=text("now()"), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=text("now()"), nullable=False)

    # Relationships
    order = relationship("Order", foreign_keys=[order_id])
    order_item = relationship("OrderItem", foreign_keys=[order_item_id])
    ticket_type = relationship("TicketType", back_populates="tickets")
    event = relationship("Event", foreign_keys=[event_id])
    transferred_from = relationship("Ticket", remote_side=[id], foreign_keys=[transferred_from_ticket_id])

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if not self.ticket_code:
            self.ticket_code = self.generate_ticket_code()
        if not self.qr_code_data:
            self.qr_code_data = self._generate_qr_data()

    @staticmethod
    def generate_ticket_code() -> str:
        """Generate a unique ticket code in format TKT-XXXXXX-XX."""
        random_hex = secrets.token_hex(4).upper()  # 8 characters
        return f"TKT-{random_hex[:6]}-{random_hex[6:8]}"

    def _generate_qr_data(self) -> str:
        """Generate signed JWT QR code data for this ticket.

        Uses cryptographic JWT signing (HS256) instead of the old
        guessable SHA256 checksum. The JWT can be verified server-side
        to prevent QR code forgery.

        If the ticket has an explicit expires_at, it is passed as the
        event_end_date hint so the JWT expiration aligns with it.
        Otherwise the signing service falls back to 30-day default.
        """
        from app.services.ticket_management.qr_signing import sign_ticket_qr

        return sign_ticket_qr(
            ticket_id=self.id,
            ticket_code=self.ticket_code,
            event_id=self.event_id,
            user_id=self.user_id,
            attendee_name=self.attendee_name,
            event_end_date=self.expires_at,
        )

    @property
    def is_valid(self) -> bool:
        """Check if ticket is valid for check-in."""
        return self.status == "valid"

    @property
    def is_checked_in(self) -> bool:
        """Check if ticket has been checked in."""
        return self.status == "checked_in"

    @property
    def can_check_in(self) -> bool:
        """Check if ticket can be checked in."""
        return self.status == "valid"

    @property
    def can_transfer(self) -> bool:
        """Check if ticket can be transferred."""
        return self.status in ("valid",)  # Can only transfer valid tickets

    @property
    def can_cancel(self) -> bool:
        """Check if ticket can be cancelled."""
        return self.status in ("valid",)  # Can only cancel valid tickets

    @property
    def qr_code_url(self) -> str:
        """Generate URL for QR code image.

        Note: This would typically point to a QR code generation service.
        For now, returns a placeholder that frontend can use to generate QR.
        """
        # In production, this might call an external QR service
        # For now, return a data URL placeholder
        return f"/api/v1/tickets/{self.id}/qr"
