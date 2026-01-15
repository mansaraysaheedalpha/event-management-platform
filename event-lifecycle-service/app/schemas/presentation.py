# app/schemas/presentation.py
from datetime import datetime
from pydantic import BaseModel, Field
from typing import List, Dict, Optional


class Presentation(BaseModel):
    id: str
    session_id: str
    slide_urls: List[str]
    status: str
    download_enabled: bool = False
    original_filename: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class PresentationUploadRequest(BaseModel):
    """
    Client sends this to request an upload URL.
    Only PDF files are allowed.
    """

    filename: str = Field(
        ...,
        min_length=1,
        max_length=255,
        json_schema_extra={"example": "keynote_presentation.pdf"},
    )
    content_type: str = Field(
        ..., json_schema_extra={"example": "application/pdf"}
    )


class PresentationUploadResponse(BaseModel):
    """
    Server responds with the URL and fields needed for a direct-to-S3 upload.
    """

    url: str
    fields: Dict[str, str]
    s3_key: str


class PresentationProcessRequest(BaseModel):
    """
    Client sends this after the S3 upload is complete to trigger processing.
    """

    s3_key: str


# Download feature schemas
class DownloadToggleRequest(BaseModel):
    """Request to enable or disable presentation download for attendees."""

    enabled: bool


class DownloadToggleResponse(BaseModel):
    """Response after toggling download availability."""

    download_enabled: bool
    message: str


class DownloadUrlResponse(BaseModel):
    """Response containing a time-limited signed URL for download."""

    url: str
    filename: str
    expires_in: int  # seconds until URL expires
