# app/schemas/session.py
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from .speaker import Speaker


class Session(BaseModel):
    id: str
    event_id: str
    title: str
    start_time: datetime
    end_time: datetime
    speakers: List[Speaker] = []
    model_config = {"from_attributes": True}


# --- THIS IS THE CORRECTED VERSION ---
class SessionCreate(BaseModel):
    title: str = Field(..., json_schema_extra={"example": "The Future of LLM's"})
    start_time: datetime  # It expects the final, combined datetime
    end_time: datetime  # It expects the final, combined datetime
    speaker_ids: Optional[List[str]] = []


# ------------------------------------


class SessionUpdate(BaseModel):
    title: Optional[str] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    speaker_ids: Optional[List[str]] = None
