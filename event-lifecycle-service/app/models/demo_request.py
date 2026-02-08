# app/models/demo_request.py
import uuid
from sqlalchemy import Column, String, Text, DateTime, text
from app.db.base_class import Base


class DemoRequest(Base):
    __tablename__ = "demo_requests"

    id = Column(
        String, primary_key=True, default=lambda: f"demo_{uuid.uuid4().hex[:12]}"
    )
    first_name = Column(String, nullable=False)
    last_name = Column(String, nullable=False)
    email = Column(String, nullable=False, index=True)
    company = Column(String, nullable=False)
    job_title = Column(String, nullable=True)
    company_size = Column(String, nullable=False)
    solution_interest = Column(String, nullable=True)
    preferred_date = Column(String, nullable=True)
    preferred_time = Column(String, nullable=True)
    message = Column(Text, nullable=True)
    status = Column(String, nullable=False, server_default=text("'pending'"))
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
