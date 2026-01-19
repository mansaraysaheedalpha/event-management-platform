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
    # User's name from the JWT token
    first_name: Optional[str] = Field(default=None, alias="firstName")
    last_name: Optional[str] = Field(default=None, alias="lastName")

    model_config = {
        "populate_by_name": True,  # Allow populating by alias
        "from_attributes": True,
    }

    @property
    def full_name(self) -> str:
        """Get the user's full name, with fallback to 'Event Organizer' if not available."""
        if self.first_name and self.last_name:
            return f"{self.first_name} {self.last_name}"
        elif self.first_name:
            return self.first_name
        elif self.last_name:
            return self.last_name
        return "Event Organizer"
