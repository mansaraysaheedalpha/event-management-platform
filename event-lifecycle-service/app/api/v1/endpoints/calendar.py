# app/api/v1/endpoints/calendar.py
"""
Calendar endpoints for ICS file generation and download.

These endpoints allow users to download calendar files (.ics) for sessions
and events, with optional personalized magic join links.
"""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import Response
from sqlalchemy.orm import Session, joinedload

from app.db.session import get_db
from app.models.session import Session as SessionModel
from app.models.event import Event as EventModel
from app.core.config import settings
from app.utils.calendar_utils import (
    generate_session_ics,
    generate_event_ics,
    generate_ics_filename,
)

router = APIRouter(tags=["Calendar"])


@router.get("/sessions/{sessionId}/calendar.ics")
async def download_session_calendar(
    sessionId: str,
    token: Optional[str] = Query(
        None, description="Magic link token for personalized join URL"
    ),
    db: Session = Depends(get_db),
):
    """
    Download ICS file for a single session.

    If a token is provided, the ICS will include a personalized magic join link.
    Otherwise, it includes the generic event URL.
    """
    # Query session with eager loading of speakers and event
    session = (
        db.query(SessionModel)
        .options(
            joinedload(SessionModel.speakers),
            joinedload(SessionModel.event),
        )
        .filter(SessionModel.id == sessionId, SessionModel.is_archived == False)
        .first()
    )

    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found",
        )

    event = session.event
    if not event or event.is_archived:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Event not found",
        )

    # Build join URL - use magic link token if provided, otherwise generic URL
    if token:
        join_url = f"{settings.FRONTEND_URL}/join?token={token}"
    else:
        join_url = f"{settings.FRONTEND_URL}/events/{event.id}/sessions/{sessionId}"

    # Extract speaker names
    speaker_names = [speaker.name for speaker in session.speakers]

    # Generate ICS content
    ics_content = generate_session_ics(
        session_id=session.id,
        session_title=session.title,
        session_description=event.description or "",
        start_time=session.start_time,
        end_time=session.end_time,
        event_name=event.name,
        organizer_name="Event Dynamics",
        organizer_email="events@eventdynamics.io",
        join_url=join_url,
        speakers=speaker_names,
    )

    # Generate filename
    filename = generate_ics_filename(session.title, is_session=True)

    return Response(
        content=ics_content,
        media_type="text/calendar",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Content-Type": "text/calendar; charset=utf-8",
        },
    )


@router.get("/events/{eventId}/calendar.ics")
async def download_event_calendar(
    eventId: str,
    userId: Optional[str] = Query(
        None, description="User ID for personalized join URLs"
    ),
    db: Session = Depends(get_db),
):
    """
    Download ICS file for an entire event with all its sessions.

    If a userId is provided, the ICS may include personalized join links
    for each session (requires additional magic link generation).
    """
    # Query event with eager loading of sessions and their speakers
    event = (
        db.query(EventModel)
        .options(
            joinedload(EventModel.sessions).joinedload(SessionModel.speakers),
        )
        .filter(EventModel.id == eventId, EventModel.is_archived == False)
        .first()
    )

    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Event not found",
        )

    # Filter out archived sessions and build session data
    sessions_data = []
    for session in event.sessions:
        if session.is_archived:
            continue

        # Build join URL for session
        if userId:
            join_url = f"{settings.FRONTEND_URL}/events/{event.id}/sessions/{session.id}?user={userId}"
        else:
            join_url = f"{settings.FRONTEND_URL}/events/{event.id}/sessions/{session.id}"

        sessions_data.append({
            "id": session.id,
            "title": session.title,
            "description": event.description,
            "start_time": session.start_time,
            "end_time": session.end_time,
            "speakers": [speaker.name for speaker in session.speakers],
            "join_url": join_url,
        })

    # Sort sessions by start time
    sessions_data.sort(key=lambda s: s["start_time"])

    # Generate ICS content
    ics_content = generate_event_ics(
        event_id=event.id,
        event_name=event.name,
        event_description=event.description or "",
        sessions=sessions_data,
        organizer_name="Event Dynamics",
        organizer_email="events@eventdynamics.io",
        base_join_url=f"{settings.FRONTEND_URL}/events/{event.id}",
    )

    # Generate filename
    filename = generate_ics_filename(event.name, is_session=False)

    return Response(
        content=ics_content,
        media_type="text/calendar",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Content-Type": "text/calendar; charset=utf-8",
        },
    )
