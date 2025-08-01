# app/schemas/token.py
from pydantic import BaseModel
from typing import Optional


class TokenPayload(BaseModel):
    sub: str  # "sub" is the standard claim for subject (user ID)
    org_id: Optional[str] = None
    exp: int  # Standard claim for expiration time
