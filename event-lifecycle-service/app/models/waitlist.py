import uuid
from sqlalchemy import Column, String, ForeignKey, DateTime, func
from app.db.base_class import Base


class WaitlistEntry(Base):
    __tablename__ = "waitlist_entries"

    id = Column(
        String, primary_key=True, default=lambda: f"wle_{uuid.uuid4().hex[:12]}"
    )
    session_id = Column(String, ForeignKey("sessions.id"), nullable=False, index=True)
    user_id = Column(String, nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
