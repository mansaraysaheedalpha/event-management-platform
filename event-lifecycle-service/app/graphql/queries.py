import strawberry
from strawberry.types import Info
from .types import EventType
from .. import crud
from typing import List

@strawberry.type
class Query:
    @strawberry.field
    def event(self, id: str, info: Info) -> EventType:
        db = info.context.db
        event = crud.event.get(db, id=id)
        return event

    @strawberry.field
    def events_by_organization(self, org_id: str, info: Info) -> List[EventType]:
        db = info.context.db
        events = crud.event.get_multi_by_organization(db, org_id=org_id)
        return events
