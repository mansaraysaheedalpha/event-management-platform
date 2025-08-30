# event-lifecycle-service/app/graphql/main.py
from ariadne import load_schema_from_path, make_executable_schema
from ariadne.asgi import GraphQL
from ariadne.asgi.handlers import GraphQLWSHandler
from .resolvers import query, mutation, event_type, speaker_type, user_type

# Load the schema from the file
type_defs = load_schema_from_path("app/graphql/schema.graphql")

# Create an executable schema
schema = make_executable_schema(type_defs, query, mutation, event_type, speaker_type, user_type)

# Create a GraphQL app instance
graphql_app = GraphQL(schema, websocket_handler=GraphQLWSHandler())
