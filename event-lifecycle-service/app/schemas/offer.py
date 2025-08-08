from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class OfferBase(BaseModel):
    event_id: str = Field(..., json_schema_extra={"example":"evt_abc"})
    title: str = Field(..., json_schema_extra={"example":"Exclusive VIP Upgrade"})
    description: Optional[str] = Field(
        None, json_schema_extra={"example":"Get backstage access and a free drink!"}
    )
    price: float = Field(..., json_schema_extra={"example":19.99})
    original_price: Optional[float] = Field(None, json_schema_extra={"example":39.99})
    currency: str = "USD"
    offer_type: str = Field(..., json_schema_extra={"example":"TICKET_UPGRADE"})
    image_url: Optional[str] = Field(None, json_schema_extra={"example":"https://example.com/vip.jpg"})
    expires_at: Optional[datetime] = None


class OfferCreate(OfferBase):
    pass


class OfferUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    price: Optional[float] = None
    original_price: Optional[float] = None
    offer_type: Optional[str] = None
    image_url: Optional[str] = None
    expires_at: Optional[datetime] = None


class Offer(OfferBase):
    id: str
    organization_id: str
    is_archived: bool

    model_config = {"from_attributes": True}
