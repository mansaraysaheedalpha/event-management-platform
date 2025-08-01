import uuid
from sqlalchemy import Column, String, ForeignKey
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import relationship
from app.db.base_class import Base


class Presentation(Base):
    __tablename__ = "presentations"

    id = Column(
        String, primary_key=True, default=lambda: f"pres_{uuid.uuid4().hex[:12]}"
    )

    # This creates a one-to-one relationship with a session
    session_id = Column(String, ForeignKey("sessions.id"), nullable=False, unique=True)

    # We will store the URLs of the processed slide images here
    slide_urls = Column(ARRAY(String), nullable=False)

    session = relationship("Session")
