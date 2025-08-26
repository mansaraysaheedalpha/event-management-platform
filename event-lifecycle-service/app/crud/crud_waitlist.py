# app/crud/crud_waitlist.py
from .base import CRUDBase
from sqlalchemy.orm import Session
from app.models.waitlist import WaitlistEntry
from app.schemas.waitlist import WaitlistEntry as WaitlistSchema


class CRUDWaitlist(CRUDBase[WaitlistEntry, WaitlistSchema, WaitlistSchema]):

    def get_first_in_queue(
        self, db: Session, *, session_id: str
    ) -> WaitlistEntry | None:
        """
        Gets the first user in the waitlist for a specific session, ordered by creation time.
        """
        return (
            db.query(self.model)
            .filter(self.model.session_id == session_id)
            .order_by(self.model.created_at.asc())
            .first()
        )


waitlist = CRUDWaitlist(WaitlistEntry)
