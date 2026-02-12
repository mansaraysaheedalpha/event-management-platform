# app/crud/crud_session_rsvp.py
"""
CRUD operations for Session RSVP management.

Handles RSVP creation, cancellation, and querying for
in-person session capacity enforcement.
"""

from typing import Optional, List
from sqlalchemy.orm import Session
from sqlalchemy import and_, func
from datetime import datetime, timezone

from app.models.session_rsvp import SessionRsvp


class CRUDSessionRsvp:
    """CRUD operations for Session RSVP."""

    def create_rsvp(
        self,
        db: Session,
        *,
        session_id: str,
        user_id: str,
        event_id: str,
    ) -> SessionRsvp:
        """Create a new RSVP for a session."""
        rsvp = SessionRsvp(
            session_id=session_id,
            user_id=user_id,
            event_id=event_id,
            status="CONFIRMED",
        )
        db.add(rsvp)
        db.commit()
        db.refresh(rsvp)
        return rsvp

    def cancel_rsvp(
        self,
        db: Session,
        *,
        session_id: str,
        user_id: str,
    ) -> Optional[SessionRsvp]:
        """Cancel a user's RSVP. Returns None if no active RSVP found."""
        rsvp = self.get_user_rsvp(db, session_id=session_id, user_id=user_id)
        if not rsvp or rsvp.status != "CONFIRMED":
            return None

        rsvp.status = "CANCELLED"
        rsvp.cancelled_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(rsvp)
        return rsvp

    def get_user_rsvp(
        self,
        db: Session,
        *,
        session_id: str,
        user_id: str,
    ) -> Optional[SessionRsvp]:
        """Get a user's RSVP for a session (any status)."""
        return db.query(SessionRsvp).filter(
            and_(
                SessionRsvp.session_id == session_id,
                SessionRsvp.user_id == user_id,
            )
        ).first()

    def get_active_rsvp(
        self,
        db: Session,
        *,
        session_id: str,
        user_id: str,
    ) -> Optional[SessionRsvp]:
        """Get a user's confirmed RSVP for a session."""
        return db.query(SessionRsvp).filter(
            and_(
                SessionRsvp.session_id == session_id,
                SessionRsvp.user_id == user_id,
                SessionRsvp.status == "CONFIRMED",
            )
        ).first()

    def get_rsvps_by_session(
        self,
        db: Session,
        *,
        session_id: str,
        status: Optional[str] = "CONFIRMED",
    ) -> List[SessionRsvp]:
        """Get all RSVPs for a session, optionally filtered by status."""
        query = db.query(SessionRsvp).filter(SessionRsvp.session_id == session_id)
        if status:
            query = query.filter(SessionRsvp.status == status)
        return query.order_by(SessionRsvp.rsvp_at.asc()).all()

    def get_rsvps_by_user(
        self,
        db: Session,
        *,
        user_id: str,
        event_id: str,
    ) -> List[SessionRsvp]:
        """Get all confirmed RSVPs for a user within an event (their schedule)."""
        return db.query(SessionRsvp).filter(
            and_(
                SessionRsvp.user_id == user_id,
                SessionRsvp.event_id == event_id,
                SessionRsvp.status == "CONFIRMED",
            )
        ).order_by(SessionRsvp.rsvp_at.asc()).all()

    def get_rsvp_count(
        self,
        db: Session,
        *,
        session_id: str,
    ) -> int:
        """Count confirmed RSVPs for a session."""
        return db.query(func.count(SessionRsvp.id)).filter(
            and_(
                SessionRsvp.session_id == session_id,
                SessionRsvp.status == "CONFIRMED",
            )
        ).scalar() or 0

    def is_user_rsvped(
        self,
        db: Session,
        *,
        session_id: str,
        user_id: str,
    ) -> bool:
        """Check if a user has an active RSVP for a session."""
        return db.query(SessionRsvp.id).filter(
            and_(
                SessionRsvp.session_id == session_id,
                SessionRsvp.user_id == user_id,
                SessionRsvp.status == "CONFIRMED",
            )
        ).first() is not None

    def reactivate_rsvp(
        self,
        db: Session,
        *,
        rsvp: SessionRsvp,
    ) -> SessionRsvp:
        """Reactivate a previously cancelled RSVP."""
        rsvp.status = "CONFIRMED"
        rsvp.cancelled_at = None
        rsvp.rsvp_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(rsvp)
        return rsvp


# Singleton instance
session_rsvp = CRUDSessionRsvp()
