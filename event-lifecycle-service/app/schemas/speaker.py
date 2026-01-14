#app/schemas/speaker.py
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
    # Optional: Link to a platform user account for backchannel access
    user_id: Optional[str] = Field(
        None,
        json_schema_extra={"example": "cmk5d9grp0001gb24ciavcgga"},
        description="Platform user ID to link speaker to their account for backchannel access",
    )


class SpeakerCreate(SpeakerBase):
    pass


class SpeakerUpdate(BaseModel):
    name: Optional[str] = None
    bio: Optional[str] = None
    expertise: Optional[List[str]] = None
    user_id: Optional[str] = None


class Speaker(SpeakerBase):
    id: str
    organization_id: str
    is_archived: bool

    model_config = {"from_attributes": True}
