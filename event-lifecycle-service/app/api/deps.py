# app/api/deps.py
from typing import Generator
from fastapi import Depends, HTTPException, status, Security
from fastapi.security import OAuth2PasswordBearer, APIKeyHeader
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from app.core.config import settings
from app.schemas.token import TokenPayload
from app.db.session import SessionLocal


def get_db() -> Generator:
    """Dependency to get database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# This tells FastAPI where to look for the token.
# The `tokenUrl` doesn't have to be a real endpoint in this service,
# it's just for the OpenAPI documentation.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")
# Optional version that doesn't raise an error when token is missing
oauth2_scheme_optional = OAuth2PasswordBearer(tokenUrl="token", auto_error=False)


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


def get_current_user_optional(
    token: str | None = Depends(oauth2_scheme_optional),
) -> TokenPayload | None:
    if token is None:
        return None
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=["HS256"])
        return TokenPayload(**payload)
    except (JWTError, ValueError):
        # If token is present but invalid, you might want to raise an error
        # or just return None depending on your security policy.
        # For this use case, returning None is fine.
        return None


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


def get_internal_api_key_optional(
    api_key: str | None = Security(api_key_header),
) -> str | None:
    """
    Returns the API key if it's valid, otherwise returns None. Does not raise an error.
    """
    if api_key == settings.INTERNAL_API_KEY:
        return api_key
    return None
