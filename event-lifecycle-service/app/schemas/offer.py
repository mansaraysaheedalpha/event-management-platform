from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class OfferBase(BaseModel):
    event_id: str = Field(..., example="evt_abc")
    title: str = Field(..., example="Exclusive VIP Upgrade")
    description: Optional[str] = Field(
        None, example="Get backstage access and a free drink!"
    )
    price: float = Field(..., example=19.99)
    original_price: Optional[float] = Field(None, example=39.99)
    currency: str = "USD"
    offer_type: str = Field(..., example="TICKET_UPGRADE")
    image_url: Optional[str] = Field(None, example="https://example.com/vip.jpg")
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

    class Config:
        from_attributes = True
