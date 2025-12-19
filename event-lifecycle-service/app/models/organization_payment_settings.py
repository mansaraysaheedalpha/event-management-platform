# app/models/organization_payment_settings.py
from sqlalchemy import Column, String, Boolean, DateTime, Integer, Numeric, ForeignKey, text
from sqlalchemy.orm import relationship
from app.db.base_class import Base
import uuid


class OrganizationPaymentSettings(Base):
    __tablename__ = "organization_payment_settings"

    id = Column(
        String, primary_key=True, default=lambda: f"ops_{uuid.uuid4().hex[:12]}"
    )
    organization_id = Column(String, nullable=False, index=True)
    provider_id = Column(String, ForeignKey("payment_providers.id"), nullable=False)
    connected_account_id = Column(String(255), nullable=True)
    payout_schedule = Column(String(50), server_default="automatic", nullable=True)
    payout_currency = Column(String(3), server_default="USD", nullable=True)
    platform_fee_percent = Column(Numeric(5, 4), server_default="0.0000", nullable=True)
    platform_fee_fixed = Column(Integer, server_default="0", nullable=True)
    is_active = Column(Boolean, nullable=False, server_default=text("true"))
    verified_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=text("now()"), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=text("now()"), nullable=False)

    # Relationships
    provider = relationship("PaymentProvider", foreign_keys=[provider_id])
