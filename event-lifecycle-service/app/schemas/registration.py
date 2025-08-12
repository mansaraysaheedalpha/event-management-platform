#app/schemas/registration.py
from pydantic import BaseModel, Field, model_validator
from typing import Optional
from enum import Enum
from datetime import datetime


class RegistrationStatus(str, Enum):
    confirmed = "confirmed"
    cancelled = "cancelled"
    checked_in = "checked_in"


class RegistrationBase(BaseModel):
    user_id: Optional[str] = None
    first_name: Optional[str] = Field(None, json_schema_extra={"example":"Guest"})
    last_name: Optional[str] = Field(None, json_schema_extra={"example":"User"})
    email: Optional[str] = Field(None, json_schema_extra={"example":"guest@example.com"})


class RegistrationCreate(RegistrationBase):
    # This validator enforces the `oneOf` logic from your spec
    @model_validator(mode="before")
    def check_user_or_guest_details(cls, values):
        user_id, email = values.get("user_id"), values.get("email")
        if not user_id and not email:
            raise ValueError("Either user_id or guest details must be provided")
        if user_id and email:
            raise ValueError("Provide either user_id or guest details, not both")
        return values


class RegistrationUpdate(BaseModel):
    status: Optional[RegistrationStatus] = None


class Registration(BaseModel):
    id: str
    event_id: str
    status: RegistrationStatus
    user_id: Optional[str] = None
    guest_email: Optional[str] = None
    guest_name: Optional[str] = None
    # ADD these two new fields
    ticket_code: str
    checked_in_at: Optional[datetime] = None

    model_config = {"from_attributes": True}
