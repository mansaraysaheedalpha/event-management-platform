# app/crud/crud_event.py
from sqlalchemy.orm import Session
from sqlalchemy.orm import joinedload
from .base import CRUDBase
from typing import List
from app.models.event import Event
from app.schemas.event import EventCreate, EventUpdate
from app.crud import crud_domain_event


class CRUDEvent(CRUDBase[Event, EventCreate, EventUpdate]):

    def get_multi_by_organization(
        self, db: Session, *, org_id: str, skip: int = 0, limit: int = 100
    ) -> List[Event]:
        """
        Overrides the base method to also filter out archived events.
        """
        return (
            db.query(self.model)
            .filter(
                self.model.organization_id == org_id,
                self.model.is_archived == False,  # <-- The missing filter
            )
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_events_count(self, db: Session, *, org_id: str) -> int:
        """
        Counts the total number of non-archived events for an organization.
        """
        return (
            db.query(self.model)
            .filter(
                self.model.organization_id == org_id, self.model.is_archived == False
            )
            .count()
        )

    def update(
        self, db: Session, *, db_obj: Event, obj_in: EventUpdate, user_id: str | None
    ) -> Event:
        change_data = {}
        update_data = obj_in.model_dump(exclude_unset=True)

        original_obj_data = {
            c.name: getattr(db_obj, c.name) for c in db_obj.__table__.columns
        }

        for field in update_data:
            if original_obj_data.get(field) != update_data[field]:
                change_data[field] = {
                    "old": original_obj_data.get(field),
                    "new": update_data[field],
                }

        # **FIX**: Call the original update method from the base class WITHOUT the user_id
        updated_event = super().update(db, db_obj=db_obj, obj_in=obj_in)

        if change_data:
            crud_domain_event.domain_event.create_log(
                db,
                event_id=db_obj.id,
                event_type="EventUpdated",
                user_id=user_id,
                data=change_data,
            )
        return updated_event

    def publish(self, db: Session, *, db_obj: Event, user_id: str | None) -> Event:
        db_obj.status = "published"
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)

        crud_domain_event.domain_event.create_log(
            db,
            event_id=db_obj.id,
            event_type="EventPublished",
            user_id=user_id,
            data={"status": "published"},
        )
        return db_obj

    def archive(self, db: Session, *, id: str, user_id: str | None) -> Event:
        # Call the original archive method from the base class
        archived_event = super().archive(db, id=id)

        crud_domain_event.domain_event.create_log(
            db,
            event_id=id,
            event_type="EventArchived",
            user_id=user_id,
            data={"is_archived": True},
        )
        return archived_event

    # ✅ --- NEW METHOD TO UPDATE IMAGE URL ---
    def update_image_url(
        self, db: Session, *, event_id: str, image_url: str
    ) -> Event | None:
        """
        Updates the imageUrl for a specific event.
        """
        event = self.get(db, id=event_id)
        if event:
            event.imageUrl = image_url
            db.add(event)
            db.commit()
            db.refresh(event)
        return event
    

    # ADD THIS NEW METHOD
    def get_sync_bundle(self, db: Session, *, event_id: str) -> Event | None:
        """
        Fetches a single event with all its related data (sessions, speakers, venue)
        eagerly loaded in one efficient query.
        """
        return (
            db.query(self.model)
            .options(
                joinedload(self.model.sessions).joinedload(Session.speakers),
                joinedload(self.model.venue),
            )
            .filter(self.model.id == event_id)
            .first()
        )


event = CRUDEvent(Event)
