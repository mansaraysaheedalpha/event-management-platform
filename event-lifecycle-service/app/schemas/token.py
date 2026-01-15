# app/schemas/token.py
from pydantic import BaseModel, Field
from typing import Optional, List


class TokenPayload(BaseModel):
    sub: str  # "sub" is the standard claim for subject (user ID)
    # This field will now correctly parse 'orgId' from the token
    # and map it to the 'org_id' attribute.
    org_id: Optional[str] = Field(default=None, alias="orgId")
    exp: int  # Standard claim for expiration time
    # Role within the organization: OWNER, ADMIN, MODERATOR, SPEAKER, MEMBER
    role: Optional[str] = None
    # Granular permissions for feature-level access control
    permissions: Optional[List[str]] = None

    model_config = {
        "populate_by_name": True,  # Allow populating by alias
        "from_attributes": True,
    }
