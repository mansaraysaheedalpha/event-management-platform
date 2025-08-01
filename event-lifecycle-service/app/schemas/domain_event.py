from pydantic import BaseModel
from typing import Optional, Dict, Any
from datetime import datetime


class DomainEvent(BaseModel):
    id: str
    event_id: str
    event_type: str
    timestamp: datetime
    user_id: Optional[str] = None
    data: Optional[Dict[str, Any]] = None

    class Config:
        from_attributes = True
