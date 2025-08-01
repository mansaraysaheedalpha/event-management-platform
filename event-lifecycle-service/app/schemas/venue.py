from pydantic import BaseModel, Field
from typing import Optional


class VenueBase(BaseModel):
    name: str = Field(..., example="Grand Convention Center")
    address: Optional[str] = Field(None, example="123 Innovation Drive, Tech City")


class VenueCreate(VenueBase):
    pass


class VenueUpdate(BaseModel):
    name: Optional[str] = None
    address: Optional[str] = None


class Venue(VenueBase):
    id: str
    organization_id: str
    is_archived: bool

    class Config:
        from_attributes = True
