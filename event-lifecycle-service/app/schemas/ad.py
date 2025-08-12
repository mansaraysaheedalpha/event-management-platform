#app/schemas/ad.py
from pydantic import BaseModel, Field
from typing import Optional


class AdBase(BaseModel):
    name: str = Field(..., example="Homepage Banner Q3")
    event_id: Optional[str] = Field(None, example="evt_abc")
    content_type: str = Field(..., example="BANNER")
    media_url: str = Field(..., json_schema_extra={"example": "https://example.com/ads/banner.jpg"})
    click_url: str = Field(..., json_schema_extra={"example": "https://example.com/product"})


class AdCreate(AdBase):
    pass


class AdUpdate(BaseModel):
    name: Optional[str] = None
    event_id: Optional[str] = None
    content_type: Optional[str] = None
    media_url: Optional[str] = None
    click_url: Optional[str] = None


class Ad(AdBase):
    id: str
    organization_id: str
    is_archived: bool

    model_config = { "form_attributes": True}
