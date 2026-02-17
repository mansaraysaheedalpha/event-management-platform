# app/models/venue_verification_document.py
import uuid
from sqlalchemy import Column, String, Text, DateTime, ForeignKey, text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.base_class import Base


class VenueVerificationDocument(Base):
    __tablename__ = "venue_verification_documents"

    id = Column(
        String, primary_key=True, default=lambda: f"vvd_{uuid.uuid4().hex[:12]}"
    )
    venue_id = Column(
        String,
        ForeignKey("venues.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    document_type = Column(String, nullable=False)  # business_registration|utility_bill|tax_certificate|other
    url = Column(String, nullable=False)
    s3_key = Column(String, nullable=False)
    filename = Column(String, nullable=False)
    status = Column(String, nullable=False, server_default=text("'uploaded'"))  # uploaded|reviewed|accepted|rejected
    admin_notes = Column(Text, nullable=True)

    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    # Relationships
    venue = relationship("Venue", back_populates="verification_documents")
