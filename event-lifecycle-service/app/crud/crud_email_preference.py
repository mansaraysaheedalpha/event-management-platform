"""CRUD operations for Email Preferences."""

import logging
from typing import Optional

from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from .base import CRUDBase
from app.models.email_preference import EmailPreference
from app.schemas.email_preference import (
    EmailPreferenceCreate,
    EmailPreferenceUpdate,
)

logger = logging.getLogger(__name__)


class CRUDEmailPreference(
    CRUDBase[EmailPreference, EmailPreferenceCreate, EmailPreferenceUpdate]
):
    """CRUD operations for email preferences."""

    def get_by_user_and_event(
        self,
        db: Session,
        *,
        user_id: str,
        event_id: Optional[str],
    ) -> Optional[EmailPreference]:
        """
        Get preference for user at specific event or global (event_id=None).
        """
        if event_id is None:
            return (
                db.query(self.model)
                .filter(
                    self.model.user_id == user_id,
                    self.model.event_id.is_(None),
                )
                .first()
            )
        return (
            db.query(self.model)
            .filter(
                self.model.user_id == user_id,
                self.model.event_id == event_id,
            )
            .first()
        )

    def get_effective_preference(
        self,
        db: Session,
        *,
        user_id: str,
        event_id: str,
    ) -> EmailPreference:
        """
        Get effective preference with fallback logic.

        Order of precedence:
        1. Event-specific preference for this user/event
        2. Global preference for this user (event_id=None)
        3. Default preference (all enabled)
        """
        # Try event-specific first
        pref = self.get_by_user_and_event(db, user_id=user_id, event_id=event_id)
        if pref:
            return pref

        # Fall back to global preference
        global_pref = self.get_by_user_and_event(db, user_id=user_id, event_id=None)
        if global_pref:
            return global_pref

        # Return default (all enabled) - not persisted
        return EmailPreference(
            id="default",
            user_id=user_id,
            event_id=event_id,
            pre_event_agenda=True,
            pre_event_networking=True,
            session_reminders=True,
        )

    def create(
        self, db: Session, *, obj_in: EmailPreferenceCreate
    ) -> Optional[EmailPreference]:
        """
        Create email preference.
        Returns None if duplicate exists (idempotent).
        """
        try:
            obj_data = obj_in.model_dump()
            db_obj = self.model(**obj_data)
            db.add(db_obj)
            db.commit()
            db.refresh(db_obj)
            return db_obj
        except IntegrityError:
            db.rollback()
            logger.debug(
                f"Duplicate preference skipped: user={obj_in.user_id}, event={obj_in.event_id}"
            )
            return None

    def upsert(
        self,
        db: Session,
        *,
        user_id: str,
        event_id: Optional[str],
        preferences: EmailPreferenceUpdate,
    ) -> EmailPreference:
        """
        Create or update email preferences.
        """
        existing = self.get_by_user_and_event(db, user_id=user_id, event_id=event_id)

        if existing:
            return self.update(db, db_obj=existing, obj_in=preferences)

        # Create new preference with provided values
        create_data = EmailPreferenceCreate(
            user_id=user_id,
            event_id=event_id,
            pre_event_agenda=preferences.pre_event_agenda
            if preferences.pre_event_agenda is not None
            else True,
            pre_event_networking=preferences.pre_event_networking
            if preferences.pre_event_networking is not None
            else True,
            session_reminders=preferences.session_reminders
            if preferences.session_reminders is not None
            else True,
        )
        result = self.create(db, obj_in=create_data)
        if result:
            return result

        # If create failed due to race condition, fetch existing
        return self.get_by_user_and_event(db, user_id=user_id, event_id=event_id)

    def should_send_pre_event_agenda(
        self,
        db: Session,
        *,
        user_id: str,
        event_id: str,
    ) -> bool:
        """Check if pre-event agenda email should be sent."""
        pref = self.get_effective_preference(db, user_id=user_id, event_id=event_id)
        return pref.pre_event_agenda

    def should_send_pre_event_networking(
        self,
        db: Session,
        *,
        user_id: str,
        event_id: str,
    ) -> bool:
        """Check if pre-event networking email should be sent."""
        pref = self.get_effective_preference(db, user_id=user_id, event_id=event_id)
        return pref.pre_event_networking


# Singleton instance
email_preference = CRUDEmailPreference(EmailPreference)
