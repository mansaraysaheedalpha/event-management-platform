from sqlalchemy.orm import Session
from jose import jwt
from app.core.config import settings
from app.schemas.token import TokenPayload


def get_user_authentication_headers(
    db: Session, org_id: str, user_id: str = "user_test"
) -> dict[str, str]:
    """
    Generates a valid JWT token and authentication headers for a test user.
    """
    payload = TokenPayload(
        sub=user_id, org_id=org_id, exp=9999999999
    )  # High expiration for tests
    token = jwt.encode(payload.model_dump(), settings.JWT_SECRET, algorithm="HS256")
    return {"Authorization": f"Bearer {token}"}
