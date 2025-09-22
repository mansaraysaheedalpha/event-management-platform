# event-lifecycle-service/app/graphql/router.py
import jwt
from strawberry.fastapi import GraphQLRouter, BaseContext
from fastapi import Depends, Request
from sqlalchemy.orm import Session
from kafka import KafkaProducer  # <-- Import KafkaProducer
from .schema import schema
from ..db.session import get_db
from ..core.config import settings
from ..core.kafka_producer import get_kafka_producer  # <-- Import the dependency getter


# --- Add 'producer' to the CustomContext ---
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


# --- Update get_context to include the producer ---
def get_context(
    request: Request,
    db: Session = Depends(get_db),
    producer: KafkaProducer = Depends(get_kafka_producer),  # <-- Inject the producer
) -> CustomContext:
    auth_header = request.headers.get("Authorization")
    user = None
    if auth_header:
        try:
            token = auth_header.split(" ")[1]
            if token:
                payload = jwt.decode(token, settings.JWT_SECRET, algorithms=["HS256"])
                user = payload
        except (jwt.PyJWTError, IndexError):
            user = None

    return CustomContext(db=db, user=user, producer=producer)  # <-- Pass the producer


graphql_router = GraphQLRouter(
    schema,
    context_getter=get_context,
)
