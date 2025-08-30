# event-lifecycle-service/app/graphql/resolvers.py
from ariadne import QueryType, MutationType, ObjectType, federated_resolver
from app.db.session import SessionLocal
from app.crud import crud_event
from app.schemas.event import EventCreate

query = QueryType()
mutation = MutationType()
event_type = ObjectType("Event")
speaker_type = ObjectType("Speaker")
user_type = ObjectType("User")

@query.field("event")
def resolve_event(_, info, id):
    db = SessionLocal()
    return crud_event.event.get(db, id=id)

@query.field("events")
def resolve_events(_, info):
    db = SessionLocal()
    # CRUDBase doesn't have a get_multi, so we query directly
    return db.query(crud_event.event.model).all()

@mutation.field("createEvent")
def resolve_create_event(_, info, name, description):
    db = SessionLocal()
    event_in = EventCreate(name=name, description=description)
    # The create_with_organization method requires an org_id.
    # For now, we will hardcode it. In a real app, this would
    # come from the authenticated user's context.
    org_id = "f47ac10b-58cc-4372-a567-0e02b2c3d479" # Dummy org_id
    return crud_event.event.create_with_organization(db, obj_in=event_in, org_id=org_id)

@federated_resolver("Event", "id")
def resolve_event_reference(_, _info, representation):
    db = SessionLocal()
    event_id = representation.get("id")
    return crud_event.event.get(db, id=event_id)

# We will need to implement this later
# @federated_resolver("User", "id")
# def resolve_user_reference(_, _info, representation):
#     # This would fetch a speaker profile from this service based on a user ID
#     # from the user-and-org-service.
#     user_id = representation.get("id")
#     # For now, return a dummy object
#     return {"id": user_id, "name": "Dummy Speaker Name"}
