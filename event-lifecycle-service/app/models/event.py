from sqlalchemy import Column, Integer, String, DateTime, Boolean, text
from app.db.base_class import Base



class Event(Base):
  __tablename__ = "events"

  id = Column(String, primary_key=True)
  organization_id = Column(String, nullable=False, index=True)
  name = Column(String, nullable=False)
  version = Column(Integer, nullable=False, server_default=text("1"))
  description = Column(String, nullable=True)
  status = Column(String, nullable=False, default="draft")
  start_date = Column(DateTime, nullable=False)
  end_date = Column(DateTime, nullable=False)
  venue_id = Column(String, nullable=True)
  is_public = Column(Boolean, nullable=False, server_default=text("false"))
   # NEW: Add a column for soft-deleting/archiving
  is_archived = Column(Boolean, nullable=False, server_default=text("false"))
  createAt = Column(DateTime, nullable=False, server_default=text("now()"))
  updatedAt = Column(DateTime, nullable=False, server_default=text("now()"))