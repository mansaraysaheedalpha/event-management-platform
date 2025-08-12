#/app/crud/crud_domain_event.py
from typing import List, Dict, Any
from sqlalchemy.orm import Session
from .base import CRUDBase
from app.models.domain_event import DomainEvent
from app.schemas.domain_event import DomainEvent as DomainEventSchema


class CRUDDomainEvent(CRUDBase[DomainEvent, DomainEventSchema, DomainEventSchema]):
    def create_log(
        self,
        db: Session,
        *,
        event_id: str,
        event_type: str,
        user_id: str | None,
        data: Dict[str, Any] | None = None
    ) -> DomainEvent:
        db_obj = self.model(
            event_id=event_id, event_type=event_type, user_id=user_id, data=data
        )
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def get_for_event(self, db: Session, *, event_id: str) -> List[DomainEvent]:
        return (
            db.query(self.model)
            .filter(self.model.event_id == event_id)
            .order_by(self.model.timestamp.asc())
            .all()
        )


domain_event = CRUDDomainEvent(DomainEvent)
