# app/graphql/schema.py

import strawberry
from strawberry.extensions import QueryDepthLimiter
from .queries import Query
from .mutations import Mutation

schema = strawberry.federation.Schema(
    query=Query,
    mutation=Mutation,
    extensions=[
        QueryDepthLimiter(max_depth=10),
    ],
)
