from pydantic import BaseModel
from datetime import datetime


class WaitlistEntry(BaseModel):
    id: str
    session_id: str
    user_id: str
    created_at: datetime

    model_config = {"form_attributes": True}
