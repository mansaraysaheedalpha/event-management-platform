from pydantic import BaseModel
from typing import List, Optional
from .event import Event
from .session import Session
from .speaker import Speaker
from .venue import Venue


class EventSyncBundle(BaseModel):
    event: Event
    sessions: List[Session] = []
    speakers: List[Speaker] = []
    venue: Optional[Venue] = None

    model_config = {"from_attributes": True }
