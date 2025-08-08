from pydantic import BaseModel, Field
from typing import Optional, List


class SpeakerBase(BaseModel):
    name: str = Field(..., json_schema_extra={"example":"Dr. Evelyn Reed"})
    bio: Optional[str] = Field(
        None, json_schema_extra={"example": "Lead AI Researcher at Futura Corp."}
    )
    expertise: Optional[List[str]] = Field(
        None, json_schema_extra={"example": ["AI", "Machine Learning"]}
    )


class SpeakerCreate(SpeakerBase):
    pass


class SpeakerUpdate(BaseModel):
    name: Optional[str] = None
    bio: Optional[str] = None
    expertise: Optional[List[str]] = None


class Speaker(SpeakerBase):
    id: str
    organization_id: str
    is_archived: bool

    model_config = {"form_attributes": True}
