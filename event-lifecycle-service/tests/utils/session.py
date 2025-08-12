from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from app.crud import crud_session
from app.schemas.session import SessionCreate
from app.models.session import Session


def create_random_session(db: Session, event_id: str) -> Session:
    """
    Creates a dummy session for testing purposes.
    """
    start_time = datetime.utcnow() + timedelta(hours=1)
    end_time = start_time + timedelta(hours=1)

    session_in = SessionCreate(
        title="Test Session", start_time=start_time, end_time=end_time
    )
    return crud_session.session.create_with_event(
        db, obj_in=session_in, event_id=event_id
    )
