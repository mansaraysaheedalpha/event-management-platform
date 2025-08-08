from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from enum import Enum
from .session import Session as SessionSchema  # Import our existing Session schema


# --- Enums for strict type validation ---
class AgendaUpdateType(str, Enum):
    SESSION_UPDATED = "SESSION_UPDATED"
    SESSION_CANCELED = "SESSION_CANCELED"
    SESSION_ADDED = "SESSION_ADDED"


class ResourceType(str, Enum):
    EVENT = "event"
    SESSION = "session"
    VENUE = "venue"


# --- Ad Content ---
class AdContent(BaseModel):
    id: str
    event_id: Optional[str] = None
    content_type: str = Field(..., alias="type")
    media_url: str
    click_url: str

    model_config = {"from_attributes": True, "populate_by_name": True}


# --- Notifications (Now with Enums and proper types) ---
class AgendaUpdateNotification(BaseModel):
    event_id: str
    update_type: AgendaUpdateType
    # The data payload is now strictly validated against our Session schema
    session_data: SessionSchema


class CapacityUpdateNotification(BaseModel):
    event_id: str
    resource_type: ResourceType
    resource_id: str
    current_level: int
    capacity: int


# --- Offers ---
class OfferContent(BaseModel):
    id: str
    event_id: str
    title: str
    description: Optional[str] = None
    price: float
    currency: str = "USD"


class WaitlistOffer(BaseModel):
    title: str
    message: str
    join_token: str
    expires_at: datetime


# --- Ticket Validation ---
class TicketValidationRequest(BaseModel):
    eventId: str
    ticketCode: str


class ValidationResult(BaseModel):
    isValid: bool
    ticketCode: str
    validatedAt: datetime
    errorReason: Optional[str] = None
