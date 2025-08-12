# app/api/v1/endpoints/sessions.py
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status, Response
from sqlalchemy.orm import Session

from app.schemas.session import Session as SessionSchema, SessionCreate, SessionUpdate
from app.schemas.token import TokenPayload
from app.api import deps
from app.db.session import get_db  # <-- CORRECT IMPORT
from app.crud import crud_session, crud_event

router = APIRouter(tags=["Sessions"])


@router.post(
    "/organizations/{orgId}/events/{eventId}/sessions",
    response_model=SessionSchema,
    status_code=status.HTTP_201_CREATED,
)
def create_session(
    orgId: str,
    eventId: str,
    session_in: SessionCreate,
    db: Session = Depends(get_db),
    current_user: TokenPayload = Depends(deps.get_current_user),
):
    """Create a new session for a specific event."""
    if current_user.org_id != orgId:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized"
        )
    event = crud_event.event.get(db, id=eventId)
    if not event or event.organization_id != orgId:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Event not found"
        )
    return crud_session.session.create_with_event(
        db=db, obj_in=session_in, event_id=eventId
    )


@router.get(
    "/organizations/{orgId}/events/{eventId}/sessions",
    response_model=List[SessionSchema],
)
def list_sessions(
    orgId: str,
    eventId: str,
    db: Session = Depends(get_db),
    current_user: TokenPayload = Depends(deps.get_current_user),
):
    """Retrieve all sessions for a specific event."""
    if current_user.org_id != orgId:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized"
        )
    return crud_session.session.get_multi_by_event(db=db, event_id=eventId)


@router.get(
    "/organizations/{orgId}/events/{eventId}/sessions/{sessionId}",
    response_model=SessionSchema,
)
def get_session(
    orgId: str,
    eventId: str,
    sessionId: str,
    db: Session = Depends(get_db),
    current_user: TokenPayload = Depends(deps.get_current_user),
):
    """Retrieve a specific session by its ID."""
    if current_user.org_id != orgId:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized"
        )
    session = crud_session.session.get(db=db, event_id=eventId, session_id=sessionId)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Session not found"
        )
    return session


@router.patch(
    "/organizations/{orgId}/events/{eventId}/sessions/{sessionId}",
    response_model=SessionSchema,
)
def update_session(
    orgId: str,
    eventId: str,
    sessionId: str,
    session_in: SessionUpdate,
    db: Session = Depends(get_db),
    current_user: TokenPayload = Depends(deps.get_current_user),
):
    """Update a session's details."""
    if current_user.org_id != orgId:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized"
        )
    session = crud_session.session.get(db=db, event_id=eventId, session_id=sessionId)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Session not found"
        )
    return crud_session.session.update(db=db, db_obj=session, obj_in=session_in)


@router.delete(
    "/organizations/{orgId}/events/{eventId}/sessions/{sessionId}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_session(
    orgId: str,
    eventId: str,
    sessionId: str,
    db: Session = Depends(get_db),
    current_user: TokenPayload = Depends(deps.get_current_user),
):
    """Soft-delete a session."""
    if current_user.org_id != orgId:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized"
        )
    session = crud_session.session.get(db=db, event_id=eventId, session_id=sessionId)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Session not found"
        )
    crud_session.session.archive(db=db, id=sessionId)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
