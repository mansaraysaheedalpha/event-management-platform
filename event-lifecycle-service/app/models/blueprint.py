import uuid
from sqlalchemy import Column, String, text
from sqlalchemy.dialects.postgresql import JSONB
from app.db.base_class import Base


class EventBlueprint(Base):
    __tablename__ = "event_blueprints"

    id = Column(String, primary_key=True, default=lambda: f"bp_{uuid.uuid4().hex[:12]}")
    organization_id = Column(String, nullable=False, index=True)
    name = Column(String, nullable=False)
    description = Column(String, nullable=True)
    # The JSONB type is specific to PostgreSQL and is highly efficient for storing JSON
    template = Column(JSONB, nullable=False)
    is_archived = Column(String, nullable=False, server_default=text("false"))
