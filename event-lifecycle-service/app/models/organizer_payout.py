# app/models/organizer_payout.py
from sqlalchemy import Column, String, Integer, Text, DateTime, text
from app.db.base_class import Base
import uuid


class OrganizerPayout(Base):
    __tablename__ = "organizer_payouts"

    id = Column(
        String, primary_key=True, default=lambda: f"po_{uuid.uuid4().hex[:12]}"
    )
    organization_id = Column(String, nullable=False, index=True)
    connected_account_id = Column(String(255), nullable=False)
    stripe_payout_id = Column(String(255), nullable=False, unique=True)
    amount = Column(Integer, nullable=False)
    currency = Column(String(3), nullable=False)
    status = Column(String(50), nullable=False)
    arrival_date = Column(DateTime(timezone=True), nullable=True)
    failure_code = Column(String(100), nullable=True)
    failure_message = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=text("now()"), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=text("now()"), nullable=False)
