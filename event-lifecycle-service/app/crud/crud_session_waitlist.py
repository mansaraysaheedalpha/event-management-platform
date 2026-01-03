# app/crud/crud_session_waitlist.py
from typing import Optional, List
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_
from datetime import datetime, timezone

from app.crud.base import CRUDBase
from app.models.session_waitlist import SessionWaitlist, WaitlistEvent
from app.schemas.waitlist import WaitlistEntryResponse, WaitlistEventCreate
from app.utils.validators import validate_status_transition, validate_priority_tier


class CRUDSessionWaitlist(CRUDBase[SessionWaitlist, WaitlistEntryResponse, WaitlistEntryResponse]):
    """
    CRUD operations for SessionWaitlist with priority queue management.
    """

    def get_by_session_and_user(
        self,
        db: Session,
        *,
        session_id: str,
        user_id: str
    ) -> Optional[SessionWaitlist]:
        """Get waitlist entry for specific session and user"""
        return db.query(self.model).filter(
            and_(
                self.model.session_id == session_id,
                self.model.user_id == user_id
            )
        ).first()

    def get_active_entry(
        self,
        db: Session,
        *,
        session_id: str,
        user_id: str
    ) -> Optional[SessionWaitlist]:
        """Get active waitlist entry (WAITING or OFFERED status)"""
        return db.query(self.model).filter(
            and_(
                self.model.session_id == session_id,
                self.model.user_id == user_id,
                self.model.status.in_(['WAITING', 'OFFERED'])
            )
        ).first()

    def get_session_waitlist(
        self,
        db: Session,
        *,
        session_id: str,
        status: Optional[str] = None
    ) -> List[SessionWaitlist]:
        """Get all waitlist entries for a session, optionally filtered by status"""
        query = db.query(self.model).filter(self.model.session_id == session_id)

        if status:
            query = query.filter(self.model.status == status)

        return query.order_by(
            self.model.priority_tier.desc(),  # VIP > PREMIUM > STANDARD
            self.model.position.asc()
        ).all()

    def get_waiting_by_priority(
        self,
        db: Session,
        *,
        session_id: str,
        priority_tier: str
    ) -> List[SessionWaitlist]:
        """Get all WAITING entries for a specific priority tier"""
        return db.query(self.model).filter(
            and_(
                self.model.session_id == session_id,
                self.model.priority_tier == priority_tier,
                self.model.status == 'WAITING'
            )
        ).order_by(self.model.joined_at.asc()).all()

    def create_entry(
        self,
        db: Session,
        *,
        session_id: str,
        user_id: str,
        priority_tier: str,
        position: int
    ) -> SessionWaitlist:
        """Create a new waitlist entry"""
        # Validate priority tier
        validated_tier = validate_priority_tier(priority_tier)

        entry = SessionWaitlist(
            session_id=session_id,
            user_id=user_id,
            priority_tier=validated_tier,
            position=position,
            status='WAITING'
        )
        db.add(entry)
        db.commit()
        db.refresh(entry)
        return entry

    def update_status(
        self,
        db: Session,
        *,
        entry: SessionWaitlist,
        status: str
    ) -> SessionWaitlist:
        """Update waitlist entry status with transition validation"""
        # Validate status transition
        validate_status_transition(entry.status, status)

        # Update status
        entry.status = status

        # Update timestamps (timezone-aware)
        if status == 'LEFT':
            entry.left_at = datetime.now(timezone.utc)
        elif status in ('ACCEPTED', 'DECLINED'):
            entry.offer_responded_at = datetime.now(timezone.utc)

        db.commit()
        db.refresh(entry)
        return entry

    def set_offer(
        self,
        db: Session,
        *,
        entry: SessionWaitlist,
        offer_token: str,
        expires_at: datetime
    ) -> SessionWaitlist:
        """Set offer details for waitlist entry"""
        # Validate status transition
        validate_status_transition(entry.status, 'OFFERED')

        entry.status = 'OFFERED'
        entry.offer_token = offer_token
        entry.offer_sent_at = datetime.now(timezone.utc)  # ✅ Timezone-aware
        entry.offer_expires_at = expires_at

        db.commit()
        db.refresh(entry)
        return entry

    def get_expired_offers(self, db: Session) -> List[SessionWaitlist]:
        """Get all offers that have expired"""
        now = datetime.now(timezone.utc)  # ✅ Timezone-aware
        return db.query(self.model).filter(
            and_(
                self.model.status == 'OFFERED',
                self.model.offer_expires_at < now
            )
        ).all()

    def update_positions(
        self,
        db: Session,
        *,
        session_id: str,
        priority_tier: str
    ) -> int:
        """
        Recalculate positions for all entries in a specific tier.
        Returns number of entries updated.
        """
        entries = self.get_waiting_by_priority(
            db,
            session_id=session_id,
            priority_tier=priority_tier
        )

        # Calculate offset based on higher priority tiers
        offset = 0
        if priority_tier == 'PREMIUM':
            vip_count = db.query(self.model).filter(
                and_(
                    self.model.session_id == session_id,
                    self.model.priority_tier == 'VIP',
                    self.model.status == 'WAITING'
                )
            ).count()
            offset = vip_count
        elif priority_tier == 'STANDARD':
            higher_tiers_count = db.query(self.model).filter(
                and_(
                    self.model.session_id == session_id,
                    self.model.priority_tier.in_(['VIP', 'PREMIUM']),
                    self.model.status == 'WAITING'
                )
            ).count()
            offset = higher_tiers_count

        # Update positions
        for idx, entry in enumerate(entries, start=1):
            entry.position = offset + idx

        db.commit()
        return len(entries)


class CRUDWaitlistEvent(CRUDBase[WaitlistEvent, WaitlistEventCreate, WaitlistEventCreate]):
    """
    CRUD operations for WaitlistEvent logging.
    """

    def log_event(
        self,
        db: Session,
        *,
        waitlist_entry_id: str,
        event_type: str,
        metadata: Optional[dict] = None
    ) -> WaitlistEvent:
        """Log a waitlist event"""
        event = WaitlistEvent(
            waitlist_entry_id=waitlist_entry_id,
            event_type=event_type,
            event_data=metadata or {}  # Using event_data instead of metadata
        )
        db.add(event)
        db.commit()
        db.refresh(event)
        return event

    def get_entry_events(
        self,
        db: Session,
        *,
        waitlist_entry_id: str
    ) -> List[WaitlistEvent]:
        """Get all events for a specific waitlist entry"""
        return db.query(self.model).filter(
            self.model.waitlist_entry_id == waitlist_entry_id
        ).order_by(self.model.created_at.desc()).all()


# Instantiate CRUD objects
session_waitlist = CRUDSessionWaitlist(SessionWaitlist)
waitlist_event = CRUDWaitlistEvent(WaitlistEvent)
