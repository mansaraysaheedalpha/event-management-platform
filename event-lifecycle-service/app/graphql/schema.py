# app/graphql/schema.py

import strawberry
from .queries import Query
from .mutations import Mutation

schema = strawberry.federation.Schema(
    query=Query,
    mutation=Mutation,
)
