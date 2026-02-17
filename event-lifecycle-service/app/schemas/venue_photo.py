# app/schemas/venue_photo.py
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime


class PhotoUploadRequest(BaseModel):
    filename: str
    content_type: str


class PhotoUploadResponse(BaseModel):
    upload_url: str
    upload_fields: dict
    s3_key: str


class PhotoUploadComplete(BaseModel):
    s3_key: str
    category: Optional[str] = None
    caption: Optional[str] = None
    is_cover: bool = False
    space_id: Optional[str] = None


class VenuePhotoUpdate(BaseModel):
    category: Optional[str] = None
    caption: Optional[str] = None
    sort_order: Optional[int] = None
    is_cover: Optional[bool] = None


class VenuePhoto(BaseModel):
    id: str
    venue_id: str
    space_id: Optional[str] = None
    url: str
    s3_key: str
    category: Optional[str] = None
    caption: Optional[str] = None
    sort_order: int = 0
    is_cover: bool = False
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class PhotoReorderRequest(BaseModel):
    photo_ids: List[str]
