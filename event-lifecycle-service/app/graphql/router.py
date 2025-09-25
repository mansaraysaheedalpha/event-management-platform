import json
import jwt
from strawberry.fastapi import GraphQLRouter, BaseContext
from fastapi import Depends, Request
from sqlalchemy.orm import Session
from kafka import KafkaProducer
from .schema import schema
from ..db.session import get_db
from ..core.config import settings
from ..core.kafka_producer import get_kafka_producer


# The context should expect all three: db, user, and producer
class CustomContext(BaseContext):
    def __init__(
        self,
        db: Session,
        user: dict | None = None,
        producer: KafkaProducer | None = None,
    ):
        self.db = db
        self.user = user
        self.producer = producer


# --- THIS IS THE FIX ---
# This function now correctly reads the 'Authorization' header passed from the gateway,
# verifies the JWT, and populates the context with the user's data.
def get_context(
    request: Request,
    db: Session = Depends(get_db),
    producer: KafkaProducer = Depends(get_kafka_producer),
) -> CustomContext:
    auth_header = request.headers.get("Authorization")
    user = None

    if auth_header:
        try:
            # The gateway passes the token in the format "Bearer <token>"
            token = auth_header.split(" ")[1]
            if token:
                # We decode the token here to get the user payload
                payload = jwt.decode(token, settings.JWT_SECRET, algorithms=["HS256"])
                user = payload
        except (jwt.PyJWTError, IndexError):
            # If the token is invalid or the header is malformed, user remains None
            user = None

    return CustomContext(db=db, user=user, producer=producer)


# ---------------------

graphql_router = GraphQLRouter(
    schema,
    context_getter=get_context,
)
