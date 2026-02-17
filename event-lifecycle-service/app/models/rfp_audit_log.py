# app/models/rfp_audit_log.py
"""
Audit trail for RFP state changes.
Tracks all critical actions: create, send, award, decline, extend, close, etc.
"""
import uuid
from sqlalchemy import Column, String, DateTime, ForeignKey, Index, text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.base_class import Base


class RFPAuditLog(Base):
    __tablename__ = "rfp_audit_log"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    rfp_id = Column(
        String, ForeignKey("rfps.id", ondelete="CASCADE"), nullable=False, index=True
    )
    rfp_venue_id = Column(
        String, ForeignKey("rfp_venues.id", ondelete="SET NULL"), nullable=True
    )
    user_id = Column(String, nullable=False, index=True)  # UUID from user service

    # Action details
    action = Column(String(50), nullable=False, index=True)
    old_state = Column(String(50), nullable=True)
    new_state = Column(String(50), nullable=True)
    action_metadata = Column(JSONB, nullable=True)  # Additional context (renamed from 'metadata' to avoid SQLAlchemy reserved name)

    # Timestamp
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    # Relationships
    rfp = relationship("RFP", backref="audit_logs")
    rfp_venue = relationship("RFPVenue", backref="audit_logs")

    __table_args__ = (
        Index("idx_audit_rfp_created_desc", "rfp_id", text("created_at DESC")),
    )
