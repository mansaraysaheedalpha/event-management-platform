from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime, timezone
from enum import Enum


class EventStatus(str, Enum):
    draft = "draft"
    published = "published"
    archived = "archived"


class Event(BaseModel):
    id: str = Field(..., json_schema_extra={"example": "evt_c5a6d8e0f9b1"})
    organization_id: str = Field(..., json_schema_extra={"example": "org_a1b2c3d4e5"})
    name: str = Field(..., json_schema_extra={"example":"Global AI Summit"})
    version: int = Field(
        ..., description="The current version number of the event state"
    )
    description: Optional[str] = Field(
        None, json_schema_extra={"example":"The premier event for AI enthusiasts"}
    )
    status: EventStatus = Field(..., json_schema_extra={"example":"published"})
    start_date: datetime
    end_date: datetime
    venue_id: Optional[str] = Field(
        None, json_schema_extra={"example": "ven_f9e8d7c6b5"}
    )
    is_public: bool = Field(
        False, description="Indicates if the event is publicly discoverable."
    )
    createdAt: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updatedAt: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = {"from_attributes": True}


class EventCreate(BaseModel):
    name: str = Field(..., json_schema_extra={"example":"Global AI Summit"})
    description: Optional[str] = Field(
        None, example="The premier event for AI enthusiasts."
    )
    start_date: datetime
    end_date: datetime
    venue_id: Optional[str] = Field(None, json_schema_extra={"example":"ven_f9e8d7c6b5"})


# NEW: Helper schema for pagination details
class Pagination(BaseModel):
    totalItems: int
    totalPages: int
    currentPage: int


# NEW: The full response model for the list endpoint
class PaginatedEvent(BaseModel):
    data: List[Event]
    pagination: Pagination


# NEW: Schema for updating an event. All fields are optional.
class EventUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    venue_id: Optional[str] = None
    is_public: Optional[bool] = None
