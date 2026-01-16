# app/models/sponsor_user.py
"""
SponsorUser model - links users to sponsors they represent.

In the real world, a sponsor company might have multiple representatives:
- Account Manager: Primary contact who manages the sponsorship
- Booth Staff: People working at the booth during the event
- Marketing Lead: Person who manages lead capture and follow-up
- Executive: VIP representative for special meetings

This is a many-to-many relationship as:
- One user can represent multiple sponsors (rare, but possible for agencies)
- One sponsor can have multiple user representatives
"""

import uuid
from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, text, UniqueConstraint
from sqlalchemy.orm import relationship
from app.db.base_class import Base


class SponsorUser(Base):
    __tablename__ = "sponsor_users"

    id = Column(
        String, primary_key=True, default=lambda: f"spusr_{uuid.uuid4().hex[:12]}"
    )
    sponsor_id = Column(String, ForeignKey("sponsors.id"), nullable=False, index=True)
    user_id = Column(String, nullable=False, index=True)  # References user in user-and-org-service

    # Role within the sponsor team
    role = Column(String(50), nullable=False, server_default=text("'representative'"))
    # Options: 'admin', 'representative', 'booth_staff', 'viewer'

    # Permissions (can override sponsor tier settings)
    can_view_leads = Column(Boolean, nullable=False, server_default=text("true"))
    can_export_leads = Column(Boolean, nullable=False, server_default=text("false"))
    can_message_attendees = Column(Boolean, nullable=False, server_default=text("false"))
    can_manage_booth = Column(Boolean, nullable=False, server_default=text("false"))
    can_invite_others = Column(Boolean, nullable=False, server_default=text("false"))

    # Status
    is_active = Column(Boolean, nullable=False, server_default=text("true"))

    # Timestamps
    joined_at = Column(DateTime(timezone=True), nullable=False, server_default=text("NOW()"))
    last_active_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    sponsor = relationship("Sponsor", back_populates="users")

    # Constraints
    __table_args__ = (
        UniqueConstraint('sponsor_id', 'user_id', name='uq_sponsor_user'),
    )
