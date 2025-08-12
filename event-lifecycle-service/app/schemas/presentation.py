#app/schemas/presentation.py
from pydantic import BaseModel, Field
from typing import List


class Presentation(BaseModel):
    id: str
    session_id: str
    slide_urls: List[str]

    model_config = {"from_attributes": True}
