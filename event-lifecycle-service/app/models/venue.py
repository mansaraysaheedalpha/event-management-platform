# app/models/venue.py
import uuid
from sqlalchemy import Column, String, text
from app.db.base_class import Base


class Venue(Base):
    __tablename__ = "venues"

    id = Column(
        String, primary_key=True, default=lambda: f"ven_{uuid.uuid4().hex[:12]}"
    )
    organization_id = Column(String, nullable=False, index=True)
    name = Column(String, nullable=False)
    address = Column(String, nullable=True)
    is_archived = Column(String, nullable=False, server_default=text("false"))
