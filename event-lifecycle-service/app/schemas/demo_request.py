# app/schemas/demo_request.py
from pydantic import BaseModel, field_validator
from typing import Optional
from datetime import datetime
import re


class DemoRequestCreate(BaseModel):
    first_name: str
    last_name: str
    email: str
    company: str
    job_title: Optional[str] = None
    company_size: str
    solution_interest: Optional[str] = None
    preferred_date: Optional[str] = None
    preferred_time: Optional[str] = None
    message: Optional[str] = None

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
        if not re.match(pattern, v) or len(v) > 254:
            raise ValueError("Invalid email address")
        return v.lower().strip()

    @field_validator("first_name", "last_name", "company")
    @classmethod
    def validate_not_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("This field cannot be empty")
        return v.strip()

    @field_validator("company_size")
    @classmethod
    def validate_company_size(cls, v: str) -> str:
        allowed = ["1-10", "11-50", "51-200", "201-500", "500+"]
        if v not in allowed:
            raise ValueError(f"Company size must be one of: {', '.join(allowed)}")
        return v


class DemoRequestResponse(BaseModel):
    id: str
    first_name: str
    last_name: str
    email: str
    company: str
    job_title: Optional[str] = None
    company_size: str
    solution_interest: Optional[str] = None
    preferred_date: Optional[str] = None
    preferred_time: Optional[str] = None
    message: Optional[str] = None
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}
