from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from app.crud import crud_event
from app.schemas.event import EventCreate
from app.models.event import Event


def create_random_event(db: Session, org_id: str) -> Event:
    """
    Creates a dummy event for testing purposes.
    """
    start_date = datetime.utcnow() + timedelta(days=10)
    end_date = start_date + timedelta(days=2)

    event_in = EventCreate(name="Test Event", start_date=start_date, end_date=end_date)
    return crud_event.event.create_with_organization(db, obj_in=event_in, org_id=org_id)
