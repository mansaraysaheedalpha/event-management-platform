# app/models/ad.py
import uuid
from sqlalchemy import Column, String, text, ForeignKey
from app.db.base_class import Base


class Ad(Base):
    __tablename__ = "ads"

    id = Column(String, primary_key=True, default=lambda: f"ad_{uuid.uuid4().hex[:12]}")
    organization_id = Column(String, nullable=False, index=True)
    event_id = Column(String, ForeignKey("events.id"), nullable=True, index=True)
    name = Column(
        String, nullable=False
    )  # For internal reference, e.g., "Homepage Banner Ad Q3"
    content_type = Column(String, nullable=False)  # e.g., BANNER, VIDEO
    media_url = Column(String, nullable=False)
    click_url = Column(String, nullable=False)
    is_archived = Column(String, nullable=False, server_default=text("false"))
