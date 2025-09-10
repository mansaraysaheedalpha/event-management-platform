# app/graphql/router.py

import json

# --- Make sure BaseContext is imported ---
from strawberry.fastapi import GraphQLRouter, BaseContext
from fastapi import Depends, Request
from sqlalchemy.orm import Session
from .schema import schema
from ..db.session import get_db


# --- THE FIX: Inherit from BaseContext ---
class CustomContext(BaseContext):
    def __init__(self, db: Session, user: dict | None = None):
        self.db = db
        self.user = user


# This function is correct
def get_context(request: Request, db: Session = Depends(get_db)) -> CustomContext:
    user_context_header = request.headers.get("x-user-context")
    user = None
    if user_context_header:
        try:
            user = json.loads(user_context_header)
        except json.JSONDecodeError:
            user = None

    return CustomContext(db=db, user=user)


# This is also correct
graphql_router = GraphQLRouter(
    schema,
    context_getter=get_context,
)
