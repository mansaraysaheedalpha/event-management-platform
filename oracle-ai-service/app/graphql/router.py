from strawberry.fastapi import GraphQLRouter
from .schema import schema

graphql_router = GraphQLRouter(schema)
