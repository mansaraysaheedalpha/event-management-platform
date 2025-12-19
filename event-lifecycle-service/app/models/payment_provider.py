# app/models/payment_provider.py
from sqlalchemy import Column, String, Boolean, DateTime, text
from sqlalchemy.dialects.postgresql import JSONB, ARRAY
from app.db.base_class import Base
import uuid


class PaymentProvider(Base):
    __tablename__ = "payment_providers"

    id = Column(
        String, primary_key=True, default=lambda: f"pp_{uuid.uuid4().hex[:12]}"
    )
    code = Column(String(50), unique=True, nullable=False)
    name = Column(String(100), nullable=False)
    is_active = Column(Boolean, nullable=False, server_default=text("true"))
    is_default = Column(Boolean, nullable=False, server_default=text("false"))
    supported_currencies = Column(ARRAY(String), server_default="{}", nullable=False)
    supported_countries = Column(ARRAY(String), server_default="{}", nullable=False)
    supported_features = Column(JSONB, server_default="{}", nullable=True)
    config = Column(JSONB, server_default="{}", nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=text("now()"), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=text("now()"), nullable=False)
