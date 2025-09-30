# app/schemas/token.py
from pydantic import BaseModel, Field
from typing import Optional


class TokenPayload(BaseModel):
    sub: str  # "sub" is the standard claim for subject (user ID)
    # This field will now correctly parse 'orgId' from the token
    # and map it to the 'org_id' attribute.
    org_id: Optional[str] = Field(default=None, alias="orgId")
    exp: int  # Standard claim for expiration time

    model_config = {
        "populate_by_name": True,  # Allow populating by alias
        "from_attributes": True,
    }
