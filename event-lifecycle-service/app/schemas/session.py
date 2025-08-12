#app/schemas/session.py
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from .speaker import Speaker  # <-- Import Speaker schema


class Session(BaseModel):
    id: str
    event_id: str
    title: str
    start_time: datetime
    end_time: datetime
    speakers: List[Speaker] = []

    model_config = { "from_attributes": True }


class SessionCreate(BaseModel):
    title: str = Field(..., json_schema_extra={"example":"The Future of LLM's"})
    start_time: datetime
    end_time: datetime
    # When creating, the client just sends a list of speaker IDs
    speaker_ids: Optional[List[str]] = []


class SessionUpdate(BaseModel):
    title: Optional[str] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None 
    speaker_ids: Optional[List[str]] = None
