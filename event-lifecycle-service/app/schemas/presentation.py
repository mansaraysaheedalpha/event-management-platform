# app/schemas/presentation.py
from pydantic import BaseModel, Field
from typing import List, Dict


class Presentation(BaseModel):
    id: str
    session_id: str
    slide_urls: List[str]
    status: str

    model_config = {"from_attributes": True}


# ** ADD THESE NEW SCHEMAS **
class PresentationUploadRequest(BaseModel):
    """
    Client sends this to request an upload URL.
    """

    filename: str = Field(..., json_schema_extra={"example""keynote_presentation.pdf"})
    content_type: str = Field(..., json_schema_extra={"example""application/pdf"})


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
