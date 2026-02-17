# app/schemas/venue_verification.py
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime


class VerificationUploadRequest(BaseModel):
    filename: str
    content_type: str
    document_type: str  # business_registration|utility_bill|tax_certificate|other


class VerificationUploadResponse(BaseModel):
    upload_url: str
    upload_fields: dict
    s3_key: str


class VerificationUploadComplete(BaseModel):
    s3_key: str
    document_type: str
    filename: str


class VenueVerificationDocument(BaseModel):
    id: str
    venue_id: str
    document_type: str
    url: str
    s3_key: str
    filename: str
    status: str = "uploaded"
    admin_notes: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}
