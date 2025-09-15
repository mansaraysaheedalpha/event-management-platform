# event-lifecycle-service/app/graphql/router.py

import json
import jwt  # ✅ Import the jwt library
from strawberry.fastapi import GraphQLRouter, BaseContext
from fastapi import Depends, Request
from sqlalchemy.orm import Session
from .schema import schema
from ..db.session import get_db
from ..core.config import settings  # ✅ Import your settings


# This class is correct and does not need to change
class CustomContext(BaseContext):
    def __init__(self, db: Session, user: dict | None = None):
        self.db = db
        self.user = user


# ✅ THIS IS THE DEFINITIVE FIX
# This function now correctly reads the 'Authorization' header,
# verifies the JWT, and populates the context.
def get_context(request: Request, db: Session = Depends(get_db)) -> CustomContext:
    auth_header = request.headers.get("Authorization")
    user = None

    if auth_header:
        try:
            # Split "Bearer <token>"
            token = auth_header.split(" ")[1]
            if token:
                # Decode the token using the same secret as the user-service
                payload = jwt.decode(token, settings.JWT_SECRET, algorithms=["HS256"])
                user = payload
        except (jwt.PyJWTError, IndexError):
            # If the token is invalid or the header is malformed, user remains None
            user = None

    return CustomContext(db=db, user=user)


# This part remains the same
graphql_router = GraphQLRouter(
    schema,
    context_getter=get_context,
)
