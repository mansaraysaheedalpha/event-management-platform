"""CRUD operations for Session Reminders."""

import logging
from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import and_, or_
from sqlalchemy.orm import Session, joinedload
from sqlalchemy.exc import IntegrityError

from .base import CRUDBase
from app.models.session_reminder import SessionReminder
from app.schemas.session_reminder import (
    SessionReminderCreate,
    SessionReminderUpdate,
    EmailStatus,
)

logger = logging.getLogger(__name__)


class CRUDSessionReminder(
    CRUDBase[SessionReminder, SessionReminderCreate, SessionReminderUpdate]
):
    """CRUD operations for session reminders."""

    def create(
        self, db: Session, *, obj_in: SessionReminderCreate
    ) -> Optional[SessionReminder]:
        """
        Create a new session reminder.
        Returns None if a duplicate reminder already exists (idempotent).
        """
        try:
            obj_data = obj_in.model_dump()
            # Convert enum to string value
            if hasattr(obj_data.get("reminder_type"), "value"):
                obj_data["reminder_type"] = obj_data["reminder_type"].value

            db_obj = self.model(**obj_data, email_status="QUEUED")
            db.add(db_obj)
            db.commit()
            db.refresh(db_obj)
            return db_obj
        except IntegrityError:
            # Duplicate reminder - this is expected behavior for idempotency
            db.rollback()
            logger.debug(
                f"Duplicate reminder skipped: session={obj_in.session_id}, "
                f"registration={obj_in.registration_id}, type={obj_in.reminder_type}"
            )
            return None

    def get_pending_reminders(
        self,
        db: Session,
        *,
        batch_size: int = 100,
    ) -> List[SessionReminder]:
        """
        Get pending reminders that are scheduled to be sent now or in the past.
        Uses eager loading for session and registration relationships.
        """
        now = datetime.now(timezone.utc)
        return (
            db.query(self.model)
            .filter(
                and_(
                    self.model.email_status == "QUEUED",
                    self.model.scheduled_at <= now,
                )
            )
            .options(
                joinedload(self.model.session),
                joinedload(self.model.registration),
            )
            .order_by(self.model.scheduled_at.asc())
            .limit(batch_size)
            .all()
        )

    def get_by_session(
        self,
        db: Session,
        *,
        session_id: str,
        reminder_type: Optional[str] = None,
    ) -> List[SessionReminder]:
        """Get all reminders for a session, optionally filtered by type."""
        query = db.query(self.model).filter(self.model.session_id == session_id)
        if reminder_type:
            query = query.filter(self.model.reminder_type == reminder_type)
        return query.all()

    def get_by_registration(
        self,
        db: Session,
        *,
        registration_id: str,
    ) -> List[SessionReminder]:
        """Get all reminders for a registration."""
        return (
            db.query(self.model)
            .filter(self.model.registration_id == registration_id)
            .all()
        )

    def reminder_exists(
        self,
        db: Session,
        *,
        registration_id: str,
        session_id: str,
        reminder_type: str,
    ) -> bool:
        """Check if a reminder already exists (for idempotency checks)."""
        return (
            db.query(self.model)
            .filter(
                and_(
                    self.model.registration_id == registration_id,
                    self.model.session_id == session_id,
                    self.model.reminder_type == reminder_type,
                )
            )
            .first()
            is not None
        )

    def mark_as_sent(
        self,
        db: Session,
        *,
        reminder_id: str,
        magic_link_token_jti: Optional[str] = None,
    ) -> Optional[SessionReminder]:
        """Mark a reminder as successfully sent."""
        reminder = self.get(db, id=reminder_id)
        if not reminder:
            return None

        reminder.email_status = EmailStatus.SENT.value
        reminder.sent_at = datetime.now(timezone.utc)
        if magic_link_token_jti:
            reminder.magic_link_token_jti = magic_link_token_jti

        db.add(reminder)
        db.commit()
        db.refresh(reminder)
        return reminder

    def mark_as_failed(
        self,
        db: Session,
        *,
        reminder_id: str,
        error_message: str,
    ) -> Optional[SessionReminder]:
        """Mark a reminder as failed with error message."""
        reminder = self.get(db, id=reminder_id)
        if not reminder:
            return None

        reminder.email_status = EmailStatus.FAILED.value
        reminder.error_message = error_message

        db.add(reminder)
        db.commit()
        db.refresh(reminder)
        return reminder

    def mark_as_delivered(
        self,
        db: Session,
        *,
        reminder_id: str,
    ) -> Optional[SessionReminder]:
        """Mark a reminder as delivered (via webhook callback)."""
        reminder = self.get(db, id=reminder_id)
        if not reminder:
            return None

        reminder.email_status = EmailStatus.DELIVERED.value

        db.add(reminder)
        db.commit()
        db.refresh(reminder)
        return reminder

    def get_failed_reminders(
        self,
        db: Session,
        *,
        limit: int = 100,
    ) -> List[SessionReminder]:
        """Get failed reminders for potential retry or dead letter processing."""
        return (
            db.query(self.model)
            .filter(self.model.email_status == "FAILED")
            .order_by(self.model.scheduled_at.asc())
            .limit(limit)
            .all()
        )

    def get_reminder_stats(
        self,
        db: Session,
        *,
        session_id: Optional[str] = None,
        event_id: Optional[str] = None,
    ) -> dict:
        """Get reminder statistics for monitoring."""
        from sqlalchemy import func

        query = db.query(
            self.model.email_status,
            func.count(self.model.id).label("count"),
        )

        if session_id:
            query = query.filter(self.model.session_id == session_id)
        if event_id:
            query = query.filter(self.model.event_id == event_id)

        results = query.group_by(self.model.email_status).all()

        stats = {status.value: 0 for status in EmailStatus}
        for status, count in results:
            stats[status] = count

        return stats


# Singleton instance
session_reminder = CRUDSessionReminder(SessionReminder)
