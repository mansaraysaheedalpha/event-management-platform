# app/api/deps.py
from fastapi import Depends, HTTPException, status, Security
from fastapi.security import OAuth2PasswordBearer, APIKeyHeader
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from app.core.config import settings
from app.schemas.token import TokenPayload

# This tells FastAPI where to look for the token.
# The `tokenUrl` doesn't have to be a real endpoint in this service,
# it's just for the OpenAPI documentation.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")


def get_current_user(token: str = Depends(oauth2_scheme)) -> TokenPayload:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        # Decode the token using the secret key
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=["HS256"])
        # Validate the payload against our schema
        token_data = TokenPayload(**payload)
    except (JWTError, ValueError):
        # Catches any error from jose or Pydantic validation
        raise credentials_exception

    return token_data

# Define the header we expect the key to be in
api_key_header = APIKeyHeader(name="X-Internal-Api-Key", auto_error=False)


def get_internal_api_key(api_key: str = Security(api_key_header)) -> str:
    """
    Checks for and validates the internal API key from the request header.
    """
    if api_key == settings.INTERNAL_API_KEY:
        return api_key
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or missing Internal API Key",
    )
