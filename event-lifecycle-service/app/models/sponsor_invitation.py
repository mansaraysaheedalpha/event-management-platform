# app/models/sponsor_invitation.py
"""
SponsorInvitation model - tracks invitations sent to sponsor representatives.

Real-world invitation flow:
1. Organizer adds a sponsor to the event
2. Organizer invites representatives by email
3. Invitee receives email with unique token link
4. Invitee clicks link -> creates account or logs in
5. Invitation is marked accepted, SponsorUser record is created
6. User now has access to sponsor portal for that event
"""

import uuid
import secrets
from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, text
from sqlalchemy.orm import relationship
from app.db.base_class import Base


def generate_invite_token():
    """Generate a secure random token for the invitation."""
    return secrets.token_urlsafe(32)


class SponsorInvitation(Base):
    __tablename__ = "sponsor_invitations"

    id = Column(
        String, primary_key=True, default=lambda: f"spinv_{uuid.uuid4().hex[:12]}"
    )
    sponsor_id = Column(String, ForeignKey("sponsors.id"), nullable=False, index=True)

    # Invitation Details
    email = Column(String(255), nullable=False, index=True)
    token = Column(String(64), nullable=False, unique=True, default=generate_invite_token)

    # Invited Role
    role = Column(String(50), nullable=False, server_default=text("'representative'"))
    # Options: 'admin', 'representative', 'booth_staff', 'viewer'

    # Permissions to grant upon acceptance
    can_view_leads = Column(Boolean, nullable=False, server_default=text("true"))
    can_export_leads = Column(Boolean, nullable=False, server_default=text("false"))
    can_message_attendees = Column(Boolean, nullable=False, server_default=text("false"))
    can_manage_booth = Column(Boolean, nullable=False, server_default=text("false"))
    can_invite_others = Column(Boolean, nullable=False, server_default=text("false"))

    # Invitation Metadata
    invited_by_user_id = Column(String, nullable=False)  # User who sent the invitation
    personal_message = Column(String(500), nullable=True)  # Optional message in invite email

    # Status
    status = Column(String(20), nullable=False, server_default=text("'pending'"))
    # Options: 'pending', 'accepted', 'declined', 'expired', 'revoked'

    # Acceptance Tracking
    accepted_by_user_id = Column(String, nullable=True)  # User who accepted (might differ from email)
    accepted_at = Column(DateTime(timezone=True), nullable=True)

    # Expiration
    expires_at = Column(DateTime(timezone=True), nullable=False)

    # Timestamps
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=text("NOW()"))
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=text("NOW()"))

    # Relationships
    sponsor = relationship("Sponsor", back_populates="invitations")
