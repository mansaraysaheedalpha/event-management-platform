# app/models/presentation.py
import uuid
from sqlalchemy import Column, String, ForeignKey, Boolean, DateTime
from sqlalchemy.dialects.postgresql import ARRAY, VARCHAR
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.base_class import Base


class Presentation(Base):
    __tablename__ = "presentations"

    id = Column(
        String, primary_key=True, default=lambda: f"pres_{uuid.uuid4().hex[:12]}"
    )

    # This creates a one-to-one relationship with a session
    session_id = Column(String, ForeignKey("sessions.id"), nullable=False, unique=True)

    # Status column: processing, ready, failed
    status = Column(
        VARCHAR(20), nullable=False, default="processing"
    )

    # We will store the URLs of the processed slide images here
    slide_urls = Column(ARRAY(String), nullable=False)

    # Download feature fields
    download_enabled = Column(Boolean, nullable=False, default=False)
    original_file_key = Column(String, nullable=True)  # S3 key of the original uploaded file
    original_filename = Column(String, nullable=True)  # Original filename for download

    # Timestamps
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )

    session = relationship("Session")
