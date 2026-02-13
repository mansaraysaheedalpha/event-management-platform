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
import logging

from app.models.session_rsvp import SessionRsvp
from app.models.session import Session as SessionModel
from app.constants.rsvp import RsvpStatus
from app.crud.crud_session_capacity import session_capacity_crud

logger = logging.getLogger(__name__)


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
            status=RsvpStatus.CONFIRMED,
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
        decrement_capacity_tracking: bool = False,
    ) -> Optional[SessionRsvp]:
        """
        Cancel a user's RSVP.

        Args:
            decrement_capacity_tracking: If True, also decrements session_capacity table
                                        atomically in same transaction

        Returns:
            SessionRsvp if cancelled, None if no active RSVP found
        """
        try:
            rsvp = self.get_user_rsvp(db, session_id=session_id, user_id=user_id)
            if not rsvp or rsvp.status != RsvpStatus.CONFIRMED:
                logger.info(
                    f"No active RSVP found for user {user_id}, session {session_id}"
                )
                return None

            rsvp.status = RsvpStatus.CANCELLED
            rsvp.cancelled_at = datetime.now(timezone.utc)

            # Decrement capacity tracking atomically in same transaction
            if decrement_capacity_tracking:
                session_capacity_crud.decrement_attendance(db, session_id)

            # Commit cancellation + decrement together
            db.commit()
            db.refresh(rsvp)

            logger.info(f"RSVP cancelled for user {user_id}, session {session_id}")
            return rsvp

        except Exception as e:
            logger.error(
                f"Failed to cancel RSVP for user {user_id}, session {session_id}: {str(e)}",
                exc_info=True,
                extra={
                    "user_id": user_id,
                    "session_id": session_id
                }
            )
            db.rollback()
            raise

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
                SessionRsvp.status == RsvpStatus.CONFIRMED,
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
                SessionRsvp.status == RsvpStatus.CONFIRMED,
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
                SessionRsvp.status == RsvpStatus.CONFIRMED,
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
                SessionRsvp.status == RsvpStatus.CONFIRMED,
            )
        ).first() is not None

    def reactivate_rsvp(
        self,
        db: Session,
        *,
        rsvp: SessionRsvp,
    ) -> SessionRsvp:
        """Reactivate a previously cancelled RSVP."""
        rsvp.status = RsvpStatus.CONFIRMED
        rsvp.cancelled_at = None
        rsvp.rsvp_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(rsvp)
        return rsvp

    def create_rsvp_with_capacity_check(
        self,
        db: Session,
        *,
        session_id: str,
        user_id: str,
        event_id: str,
        max_capacity: Optional[int] = None,
        increment_capacity_tracking: bool = True,
    ) -> tuple[Optional[SessionRsvp], bool]:
        """
        Atomically check capacity, create RSVP, and update capacity tracking.

        All operations happen in a single transaction to ensure data consistency.

        Args:
            increment_capacity_tracking: If True, also increments session_capacity table

        Returns:
            (rsvp, success) where success is False if capacity exceeded
        """
        try:
            # Start transaction with SELECT FOR UPDATE to prevent race conditions
            # Lock the session row to prevent concurrent capacity violations
            session_obj = db.query(SessionModel).filter(
                SessionModel.id == session_id
            ).with_for_update().first()

            if not session_obj:
                logger.warning(f"Session {session_id} not found during RSVP creation")
                return None, False

            # Check capacity within locked transaction
            if max_capacity is not None:
                current_count = self.get_rsvp_count(db, session_id=session_id)
                if current_count >= max_capacity:
                    logger.info(
                        f"RSVP rejected for user {user_id} - session {session_id} at capacity "
                        f"({current_count}/{max_capacity})"
                    )
                    db.rollback()
                    return None, False

            # Create RSVP
            rsvp = SessionRsvp(
                session_id=session_id,
                user_id=user_id,
                event_id=event_id,
                status=RsvpStatus.CONFIRMED,
            )
            db.add(rsvp)

            # Increment capacity tracking atomically in same transaction
            if increment_capacity_tracking:
                session_capacity_crud.increment_attendance(db, session_id)

            # Commit everything together - RSVP + capacity in one atomic operation
            db.commit()
            db.refresh(rsvp)

            logger.info(f"RSVP created successfully for user {user_id}, session {session_id}")
            return rsvp, True

        except Exception as e:
            logger.error(
                f"Failed to create RSVP for user {user_id}, session {session_id}: {str(e)}",
                exc_info=True,
                extra={
                    "user_id": user_id,
                    "session_id": session_id,
                    "event_id": event_id,
                    "max_capacity": max_capacity
                }
            )
            db.rollback()
            raise

    def reactivate_rsvp_with_capacity_check(
        self,
        db: Session,
        *,
        rsvp: SessionRsvp,
        max_capacity: Optional[int] = None,
        increment_capacity_tracking: bool = True,
    ) -> tuple[Optional[SessionRsvp], bool]:
        """
        Atomically check capacity, reactivate RSVP, and update capacity tracking.

        All operations happen in a single transaction to ensure data consistency.

        Args:
            increment_capacity_tracking: If True, also increments session_capacity table

        Returns:
            (rsvp, success) where success is False if capacity exceeded
        """
        try:
            # Start transaction with SELECT FOR UPDATE
            session_obj = db.query(SessionModel).filter(
                SessionModel.id == rsvp.session_id
            ).with_for_update().first()

            if not session_obj:
                logger.warning(f"Session {rsvp.session_id} not found during RSVP reactivation")
                return None, False

            # Check capacity within locked transaction
            if max_capacity is not None:
                current_count = self.get_rsvp_count(db, session_id=rsvp.session_id)
                if current_count >= max_capacity:
                    logger.info(
                        f"RSVP reactivation rejected for user {rsvp.user_id} - "
                        f"session {rsvp.session_id} at capacity ({current_count}/{max_capacity})"
                    )
                    db.rollback()
                    return None, False

            # Reactivate RSVP (preserve original rsvp_at timestamp for fairness)
            rsvp.status = RsvpStatus.CONFIRMED
            rsvp.cancelled_at = None
            # Don't update rsvp_at - preserve original timestamp

            # Increment capacity tracking atomically in same transaction
            if increment_capacity_tracking:
                session_capacity_crud.increment_attendance(db, rsvp.session_id)

            # Commit everything together
            db.commit()
            db.refresh(rsvp)

            logger.info(
                f"RSVP reactivated successfully for user {rsvp.user_id}, session {rsvp.session_id}"
            )
            return rsvp, True

        except Exception as e:
            logger.error(
                f"Failed to reactivate RSVP for user {rsvp.user_id}, session {rsvp.session_id}: {str(e)}",
                exc_info=True,
                extra={
                    "user_id": rsvp.user_id,
                    "session_id": rsvp.session_id,
                    "max_capacity": max_capacity
                }
            )
            db.rollback()
            raise


# Singleton instance
session_rsvp = CRUDSessionRsvp()
