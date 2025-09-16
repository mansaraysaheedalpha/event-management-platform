# app/crud/crud_event.py
from sqlalchemy.orm import Session
from sqlalchemy import func
from sqlalchemy.orm import joinedload
from .base import CRUDBase
from typing import List
from app.models.event import Event
from app.schemas.event import EventCreate, EventUpdate
from app.crud import crud_domain_event


class CRUDEvent(CRUDBase[Event, EventCreate, EventUpdate]):

    def get_multi_by_organization(
        self,
        db: Session,
        *,
        org_id: str,
        skip: int = 0,
        limit: int = 100,
        search: str | None = None,
        status: str | None = None,
        sort_by: str | None = "start_date",
        sort_direction: str | None = "desc",
    ) -> dict:
        """
        Gets a list of events for an organization with optional filters, sorting, and pagination.
        Also returns the total count of events that match the filters.
        """
        query = db.query(self.model).filter(
            self.model.organization_id == org_id,
            self.model.is_archived == False,
        )

        # Filtering
        if search:
            query = query.filter(self.model.name.ilike(f"%{search}%"))
        if status:
            query = query.filter(self.model.status == status)

        # Get total count before pagination
        total_count = query.count()

        # Sorting
        sort_attr = getattr(self.model, sort_by, self.model.start_date)
        if sort_direction and sort_direction.lower() == "desc":
            query = query.order_by(sort_attr.desc())
        else:
            query = query.order_by(sort_attr.asc())

        # Pagination
        query = query.offset(skip).limit(limit)

        events = query.all()

        # Efficiently fetch registration counts
        event_ids = [event.id for event in events]
        if not event_ids:
            return {"events": [], "totalCount": total_count}

        from app.models.registration import Registration
        from sqlalchemy import func

        registration_counts = (
            db.query(Registration.event_id, func.count(Registration.id).label("count"))
            .filter(Registration.event_id.in_(event_ids))
            .group_by(Registration.event_id)
            .all()
        )

        counts_map = {event_id: count for event_id, count in registration_counts}

        # Prepare results as dictionaries
        event_dicts = []
        for event in events:
            event_dict = {
                c.name: getattr(event, c.name) for c in event.__table__.columns
            }
            event_dict["registrationsCount"] = counts_map.get(event.id, 0)
            event_dicts.append(event_dict)

        return {"events": event_dicts, "totalCount": total_count}

    def get_event_stats(self, db: Session, *, org_id: str) -> dict:
        """
        Calculates dashboard statistics for an organization.
        """
        from app.models.registration import Registration
        from datetime import datetime

        # Total non-archived events
        total_events = (
            db.query(self.model)
            .filter(
                self.model.organization_id == org_id,
                self.model.is_archived == False,
            )
            .count()
        )

        # Upcoming non-archived events
        upcoming_events = (
            db.query(self.model)
            .filter(
                self.model.organization_id == org_id,
                self.model.is_archived == False,
                self.model.start_date > datetime.utcnow(),
            )
            .count()
        )

        # Total registrations for all non-archived events in the organization
        total_registrations = (
            db.query(func.count(Registration.id))
            .join(self.model, self.model.id == Registration.event_id)
            .filter(
                self.model.organization_id == org_id,
                self.model.is_archived == False,
            )
            .scalar()
        )

        return {
            "totalEvents": total_events,
            "upcomingEvents": upcoming_events,
            "totalRegistrations": total_registrations,
        }

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
