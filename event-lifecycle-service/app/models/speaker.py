import uuid
from sqlalchemy import Column, String, text
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import ARRAY
from app.db.base_class import Base
from app.models.session_speaker import session_speaker_association


class Speaker(Base):
    __tablename__ = "speakers"

    id = Column(
        String, primary_key=True, default=lambda: f"spk_{uuid.uuid4().hex[:12]}"
    )
    organization_id = Column(String, nullable=False, index=True)
    name = Column(String, nullable=False)
    bio = Column(String, nullable=True)
    expertise = Column(ARRAY(String), nullable=True)
    is_archived = Column(String, nullable=False, server_default=text("false"))

    # This creates the "many" side of the many-to-many relationship
    sessions = relationship(
        "Session", secondary=session_speaker_association, back_populates="speakers"
    )
