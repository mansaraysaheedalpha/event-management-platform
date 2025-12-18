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
    chat_enabled: bool = True
    qa_enabled: bool = True
    polls_enabled: bool = True
    chat_open: bool = False
    qa_open: bool = False
    polls_open: bool = False
    speakers: List[Speaker] = []
    # Optional organization_id - populated from the event relationship for internal API calls
    organization_id: Optional[str] = None
    model_config = {"from_attributes": True}


# --- THIS IS THE CORRECTED VERSION ---
class SessionCreate(BaseModel):
    title: str = Field(..., json_schema_extra={"example": "The Future of LLM's"})
    start_time: datetime  # It expects the final, combined datetime
    end_time: datetime  # It expects the final, combined datetime
    speaker_ids: Optional[List[str]] = []
    chat_enabled: bool = True  # Defaults to enabled
    qa_enabled: bool = True  # Defaults to enabled
    polls_enabled: bool = True  # Defaults to enabled


# ------------------------------------


class SessionUpdate(BaseModel):
    title: Optional[str] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    speaker_ids: Optional[List[str]] = None
    chat_enabled: Optional[bool] = None
    qa_enabled: Optional[bool] = None
    polls_enabled: Optional[bool] = None
    chat_open: Optional[bool] = None
    qa_open: Optional[bool] = None
    polls_open: Optional[bool] = None
