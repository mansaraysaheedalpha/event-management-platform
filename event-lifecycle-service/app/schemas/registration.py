from pydantic import BaseModel, Field, validator
from typing import Optional
from enum import Enum
from datetime import datetime


class RegistrationStatus(str, Enum):
    confirmed = "confirmed"
    cancelled = "cancelled"
    checked_in = "checked_in"


class RegistrationBase(BaseModel):
    user_id: Optional[str] = None
    first_name: Optional[str] = Field(None, example="Guest")
    last_name: Optional[str] = Field(None, example="User")
    email: Optional[str] = Field(None, example="guest@example.com")


class RegistrationCreate(RegistrationBase):
    # This validator enforces the `oneOf` logic from your spec
    @validator("user_id", always=True)
    def check_user_or_guest_details(cls, v, values):
        if v is None and values.get("email") is None:
            raise ValueError(
                "Either user_id or guest details (first_name, last_name, email) must be provided"
            )
        if v is not None and values.get("email") is not None:
            raise ValueError("Provide either user_id or guest details, not both")
        return v


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

    class Config:
        from_attributes = True
