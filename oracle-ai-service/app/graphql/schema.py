import strawberry
from .queries import Query

schema = strawberry.federation.Schema(
    query=Query,
)
