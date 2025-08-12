# app/api/v1/endpoints/public.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.schemas.event import Event as EventSchema
from app.db.session import get_db
from app.crud import crud_event 

router = APIRouter(tags=["Public"])


@router.get("/public/events/{eventId}", response_model=EventSchema)
def get_public_event_by_id(eventId: str, db: Session = Depends(get_db)):
    """
    Retrieves the publicly viewable details of a single event.
    """
    # NEW: Call the get method from the crud_event.event object
    event = crud_event.event.get(db, id=eventId)

    if not event or event.is_archived or not event.is_public:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Event with ID {eventId} not found",
        )
    return event
