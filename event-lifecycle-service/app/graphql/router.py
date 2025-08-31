from strawberry.fastapi import GraphQLRouter, BaseContext
from strawberry.types import Info
from ..db.session import SessionLocal
from fastapi import Depends
from sqlalchemy.orm import Session
from .schema import schema

class CustomContext(BaseContext):
    def __init__(self, db: Session = Depends(SessionLocal)):
        self.db = db

def get_context(custom_context: CustomContext = Depends()):
    return custom_context

graphql_router = GraphQLRouter(schema, context_getter=get_context)
