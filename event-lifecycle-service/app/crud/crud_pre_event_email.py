"""CRUD operations for Pre-Event Emails."""

import logging
from datetime import datetime, date, timezone
from typing import List, Optional

from sqlalchemy import and_
from sqlalchemy.orm import Session, joinedload
from sqlalchemy.exc import IntegrityError

from .base import CRUDBase
from app.models.pre_event_email import PreEventEmail
from app.schemas.pre_event_email import (
    PreEventEmailCreate,
    PreEventEmailUpdate,
    PreEventEmailStatus,
)

logger = logging.getLogger(__name__)


class CRUDPreEventEmail(
    CRUDBase[PreEventEmail, PreEventEmailCreate, PreEventEmailUpdate]
):
    """CRUD operations for pre-event emails."""

    def create(
        self, db: Session, *, obj_in: PreEventEmailCreate
    ) -> Optional[PreEventEmail]:
        """
        Create a new pre-event email record.
        Returns None if a duplicate already exists (idempotent).
        """
        try:
            obj_data = obj_in.model_dump()
            # Convert enum to string value
            if hasattr(obj_data.get("email_type"), "value"):
                obj_data["email_type"] = obj_data["email_type"].value

            db_obj = self.model(**obj_data, email_status="QUEUED")
            db.add(db_obj)
            db.commit()
            db.refresh(db_obj)
            return db_obj
        except IntegrityError:
            # Duplicate email - this is expected behavior for idempotency
            db.rollback()
            logger.debug(
                f"Duplicate pre-event email skipped: "
                f"reg={obj_in.registration_id}, event={obj_in.event_id}, "
                f"type={obj_in.email_type}, date={obj_in.email_date}"
            )
            return None

    def get_pending_emails(
        self,
        db: Session,
        *,
        batch_size: int = 100,
    ) -> List[PreEventEmail]:
        """
        Get pending emails that are scheduled to be sent now or in the past.
        Uses eager loading for registration and event relationships.
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
                joinedload(self.model.registration),
                joinedload(self.model.event),
            )
            .order_by(self.model.scheduled_at.asc())
            .limit(batch_size)
            .all()
        )

    def get_by_event(
        self,
        db: Session,
        *,
        event_id: str,
        email_type: Optional[str] = None,
        email_date: Optional[date] = None,
    ) -> List[PreEventEmail]:
        """Get all pre-event emails for an event."""
        query = db.query(self.model).filter(self.model.event_id == event_id)
        if email_type:
            query = query.filter(self.model.email_type == email_type)
        if email_date:
            query = query.filter(self.model.email_date == email_date)
        return query.all()

    def get_by_registration(
        self,
        db: Session,
        *,
        registration_id: str,
    ) -> List[PreEventEmail]:
        """Get all pre-event emails for a registration."""
        return (
            db.query(self.model)
            .filter(self.model.registration_id == registration_id)
            .all()
        )

    def email_already_queued(
        self,
        db: Session,
        *,
        registration_id: str,
        event_id: str,
        email_type: str,
        email_date: date,
    ) -> bool:
        """Check if an email already exists (for idempotency checks)."""
        return (
            db.query(self.model)
            .filter(
                and_(
                    self.model.registration_id == registration_id,
                    self.model.event_id == event_id,
                    self.model.email_type == email_type,
                    self.model.email_date == email_date,
                )
            )
            .first()
            is not None
        )

    def mark_as_sent(
        self,
        db: Session,
        *,
        email_id: str,
        resend_message_id: Optional[str] = None,
    ) -> Optional[PreEventEmail]:
        """Mark an email as successfully sent."""
        email = self.get(db, id=email_id)
        if not email:
            return None

        email.email_status = PreEventEmailStatus.SENT.value
        email.sent_at = datetime.now(timezone.utc)
        if resend_message_id:
            email.resend_message_id = resend_message_id

        db.add(email)
        db.commit()
        db.refresh(email)
        return email

    def mark_as_failed(
        self,
        db: Session,
        *,
        email_id: str,
        error_message: str,
    ) -> Optional[PreEventEmail]:
        """Mark an email as failed with error message."""
        email = self.get(db, id=email_id)
        if not email:
            return None

        email.email_status = PreEventEmailStatus.FAILED.value
        email.error_message = error_message

        db.add(email)
        db.commit()
        db.refresh(email)
        return email

    def mark_as_delivered(
        self,
        db: Session,
        *,
        email_id: str,
    ) -> Optional[PreEventEmail]:
        """Mark an email as delivered (via webhook callback)."""
        email = self.get(db, id=email_id)
        if not email:
            return None

        email.email_status = PreEventEmailStatus.DELIVERED.value

        db.add(email)
        db.commit()
        db.refresh(email)
        return email

    def get_failed_emails(
        self,
        db: Session,
        *,
        event_id: Optional[str] = None,
        limit: int = 100,
    ) -> List[PreEventEmail]:
        """Get failed emails for potential retry or dead letter processing."""
        query = db.query(self.model).filter(self.model.email_status == "FAILED")
        if event_id:
            query = query.filter(self.model.event_id == event_id)
        return query.order_by(self.model.scheduled_at.asc()).limit(limit).all()

    def get_email_stats(
        self,
        db: Session,
        *,
        event_id: Optional[str] = None,
        email_date: Optional[date] = None,
    ) -> dict:
        """Get email statistics for monitoring."""
        from sqlalchemy import func

        query = db.query(
            self.model.email_status,
            self.model.email_type,
            func.count(self.model.id).label("count"),
        )

        if event_id:
            query = query.filter(self.model.event_id == event_id)
        if email_date:
            query = query.filter(self.model.email_date == email_date)

        results = query.group_by(
            self.model.email_status,
            self.model.email_type,
        ).all()

        stats = {}
        for status, email_type, count in results:
            if email_type not in stats:
                stats[email_type] = {}
            stats[email_type][status] = count

        return stats


# Singleton instance
pre_event_email = CRUDPreEventEmail(PreEventEmail)
