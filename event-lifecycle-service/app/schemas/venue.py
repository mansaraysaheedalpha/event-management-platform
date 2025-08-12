from pydantic import BaseModel, Field
from typing import Optional


class VenueBase(BaseModel):
    name: str = Field(..., json_schema_extra={"example":"Grand Convention Center"})
    address: Optional[str] = Field(None, json_schema_extra={"example":"123 Innovation Drive, Tech City"})


class VenueCreate(VenueBase):
    pass


class VenueUpdate(BaseModel):
    name: Optional[str] = None
    address: Optional[str] = None


class Venue(VenueBase):
    id: str
    organization_id: str
    is_archived: bool

    model_config = {"form_attributes": True}
