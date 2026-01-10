# app/graphql/waitlist_queries.py
"""
GraphQL Query Resolvers for Waitlist Management.

Provides query endpoints for:
- Getting waitlist position
- Viewing waitlist entries
- Session capacity information
- Waitlist analytics
"""

import strawberry
from typing import Optional, List
from strawberry.types import Info
from fastapi import HTTPException

from .. import crud
from ..crud.crud_session_capacity import session_capacity_crud
from ..crud.crud_waitlist_analytics import waitlist_analytics_crud
from ..utils.waitlist import (
    calculate_waitlist_position,
    get_total_waiting,
    estimate_wait_time
)
from ..utils.waitlist_analytics import get_event_analytics
from ..utils.session_utils import check_session_capacity
from ..db.redis import redis_client
from .waitlist_types import (
    WaitlistEntryType,
    WaitlistUserType,
    WaitlistPositionType,
    SessionCapacityType,
    WaitlistStatsType,
    WaitlistStatsByPriorityType,
    EventWaitlistAnalyticsType,
    WaitlistStatus,
    PriorityTier
)
from ..utils.user_service import get_users_info_batch


def _convert_waitlist_entry(entry, user_info: dict = None) -> WaitlistEntryType:
    """Convert database waitlist entry to GraphQL type"""
    user = None
    if user_info:
        user = WaitlistUserType(
            id=user_info.get("id", entry.user_id),
            email=user_info.get("email", ""),
            first_name=user_info.get("firstName", ""),
            last_name=user_info.get("lastName", ""),
            image_url=user_info.get("imageUrl"),
        )

    return WaitlistEntryType(
        id=entry.id,
        session_id=entry.session_id,
        user_id=entry.user_id,
        user=user,
        status=WaitlistStatus[entry.status],
        priority_tier=PriorityTier[entry.priority_tier],
        position=entry.position,
        joined_at=entry.joined_at,
        offer_sent_at=entry.offer_sent_at,
        offer_expires_at=entry.offer_expires_at,
        offer_responded_at=entry.offer_responded_at,
        left_at=entry.left_at
    )


async def _convert_waitlist_entries_with_users(entries) -> List[WaitlistEntryType]:
    """Convert multiple waitlist entries and fetch user info in batch"""
    if not entries:
        return []

    # Get all user IDs
    user_ids = [entry.user_id for entry in entries]

    # Batch fetch user info
    users_info = await get_users_info_batch(user_ids)

    # Convert entries with user info
    return [
        _convert_waitlist_entry(entry, users_info.get(entry.user_id))
        for entry in entries
    ]


@strawberry.type
class WaitlistQuery:
    """Waitlist query resolvers"""

    @strawberry.field
    def my_waitlist_position(
        self,
        session_id: strawberry.ID,
        info: Info
    ) -> Optional[WaitlistPositionType]:
        """
        Get current user's position in waitlist for a session.

        Returns None if user is not on waitlist.
        Requires authentication.
        """
        user = info.context.user
        if not user:
            raise HTTPException(status_code=401, detail="Authentication required")

        user_id = user.get("sub")
        db = info.context.db
        session_id_str = str(session_id)

        # Get waitlist entry
        entry = crud.waitlist.get_active_entry(
            db,
            session_id=session_id_str,
            user_id=user_id
        )

        if not entry:
            return None

        # Calculate position
        from ..utils.waitlist import calculate_waitlist_position
        position = calculate_waitlist_position(
            session_id=session_id_str,
            priority_tier=entry.priority_tier,
            joined_at=entry.joined_at,
            db=db
        )

        # Get total waiting from Redis
        total = get_total_waiting(session_id_str, redis_client)

        # Estimate wait time
        estimated_wait = estimate_wait_time(session_id_str, position, db)

        return WaitlistPositionType(
            position=position,
            total=total,
            estimated_wait_minutes=estimated_wait,
            priority_tier=PriorityTier[entry.priority_tier],
            status=WaitlistStatus[entry.status]
        )

    @strawberry.field
    def my_waitlist_entry(
        self,
        session_id: strawberry.ID,
        info: Info
    ) -> Optional[WaitlistEntryType]:
        """
        Get current user's waitlist entry for a session.

        Returns None if user is not on waitlist.
        Requires authentication.
        """
        user = info.context.user
        if not user:
            raise HTTPException(status_code=401, detail="Authentication required")

        user_id = user.get("sub")
        db = info.context.db
        session_id_str = str(session_id)

        # Get waitlist entry
        entry = crud.waitlist.get_active_entry(
            db,
            session_id=session_id_str,
            user_id=user_id
        )

        if not entry:
            return None

        return _convert_waitlist_entry(entry)

    @strawberry.field
    def my_waitlist_entries(self, info: Info) -> List[WaitlistEntryType]:
        """
        Get all waitlist entries for current user across all sessions.

        Requires authentication.
        """
        user = info.context.user
        if not user:
            raise HTTPException(status_code=401, detail="Authentication required")

        user_id = user.get("sub")
        db = info.context.db

        # Query all waitlist entries for user
        from ..models.session_waitlist import SessionWaitlist
        entries = db.query(SessionWaitlist).filter(
            SessionWaitlist.user_id == user_id,
            SessionWaitlist.status.in_(['WAITING', 'OFFERED'])
        ).all()

        return [_convert_waitlist_entry(entry) for entry in entries]

    @strawberry.field
    def session_capacity(
        self,
        session_id: strawberry.ID,
        info: Info
    ) -> SessionCapacityType:
        """
        Get capacity information for a session.

        Public - no authentication required.
        """
        db = info.context.db
        session_id_str = str(session_id)

        # Use existing utility function
        capacity_info = check_session_capacity(db, session_id_str)

        # Get waitlist count from Redis
        waitlist_count = get_total_waiting(session_id_str, redis_client)

        return SessionCapacityType(
            session_id=session_id_str,
            maximum_capacity=capacity_info["capacity"],
            current_attendance=capacity_info["current"],
            available_spots=capacity_info["available"],
            is_available=not capacity_info["is_full"],
            waitlist_count=waitlist_count
        )

    @strawberry.field
    async def session_waitlist(
        self,
        session_id: strawberry.ID,
        status_filter: Optional[str] = None,
        info: Info = None
    ) -> List[WaitlistEntryType]:
        """
        [ADMIN] Get all waitlist entries for a session with user info.

        Requires admin or organizer authorization.
        """
        user = info.context.user
        if not user:
            raise HTTPException(status_code=401, detail="Authentication required")

        db = info.context.db
        session_id_str = str(session_id)

        # Check authorization - must be organizer
        from ..models.session import Session as SessionModel
        from ..models.event import Event as EventModel

        session_obj = db.query(SessionModel).filter(
            SessionModel.id == session_id_str
        ).first()

        if not session_obj:
            raise HTTPException(status_code=404, detail="Session not found")

        event = db.query(EventModel).filter(
            EventModel.id == session_obj.event_id
        ).first()

        if not event:
            raise HTTPException(status_code=404, detail="Event not found")

        user_id = user.get("sub")
        user_org_id = user.get("orgId")

        # Authorization check
        if event.owner_id != user_id and (not user_org_id or event.organization_id != user_org_id):
            raise HTTPException(
                status_code=403,
                detail="Not authorized to view waitlist"
            )

        # Get entries
        entries = crud.waitlist.get_session_waitlist(
            db,
            session_id=session_id_str,
            status=status_filter
        )

        # Return entries with user info (fetched in batch)
        return await _convert_waitlist_entries_with_users(entries)

    @strawberry.field
    def session_waitlist_stats(
        self,
        session_id: strawberry.ID,
        info: Info
    ) -> WaitlistStatsType:
        """
        [ADMIN] Get waitlist statistics for a session.

        Requires admin or organizer authorization.
        """
        user = info.context.user
        if not user:
            raise HTTPException(status_code=401, detail="Authentication required")

        db = info.context.db
        session_id_str = str(session_id)

        # Authorization check (same as above)
        from ..models.session import Session as SessionModel
        from ..models.event import Event as EventModel

        session_obj = db.query(SessionModel).filter(
            SessionModel.id == session_id_str
        ).first()

        if not session_obj:
            raise HTTPException(status_code=404, detail="Session not found")

        event = db.query(EventModel).filter(
            EventModel.id == session_obj.event_id
        ).first()

        user_id = user.get("sub")
        user_org_id = user.get("orgId")

        if event.owner_id != user_id and (not user_org_id or event.organization_id != user_org_id):
            raise HTTPException(status_code=403, detail="Not authorized")

        # Get stats
        from sqlalchemy import func
        from ..models.session_waitlist import SessionWaitlist

        status_counts = db.query(
            SessionWaitlist.status,
            func.count(SessionWaitlist.id)
        ).filter(
            SessionWaitlist.session_id == session_id_str
        ).group_by(SessionWaitlist.status).all()

        status_dict = {status: count for status, count in status_counts}

        # Get priority breakdown
        priority_counts = db.query(
            SessionWaitlist.priority_tier,
            func.count(SessionWaitlist.id)
        ).filter(
            SessionWaitlist.session_id == session_id_str,
            SessionWaitlist.status == 'WAITING'
        ).group_by(SessionWaitlist.priority_tier).all()

        priority_dict = {tier: count for tier, count in priority_counts}

        # Get Redis counts (if available)
        redis_vip = 0
        redis_premium = 0
        redis_standard = 0
        try:
            import redis
            from ..api.deps import get_redis
            redis_client = next(get_redis())
            redis_vip = redis_client.zcard(f"waitlist:session:{session_id_str}:vip") or 0
            redis_premium = redis_client.zcard(f"waitlist:session:{session_id_str}:premium") or 0
            redis_standard = redis_client.zcard(f"waitlist:session:{session_id_str}:standard") or 0
        except Exception:
            pass

        return WaitlistStatsType(
            session_id=session_id_str,
            total_waiting=status_dict.get('WAITING', 0),
            total_offered=status_dict.get('OFFERED', 0),
            total_accepted=status_dict.get('ACCEPTED', 0),
            total_declined=status_dict.get('DECLINED', 0),
            total_expired=status_dict.get('EXPIRED', 0),
            total_left=status_dict.get('LEFT', 0),
            by_priority=WaitlistStatsByPriorityType(
                vip=priority_dict.get('VIP', 0),
                premium=priority_dict.get('PREMIUM', 0),
                standard=priority_dict.get('STANDARD', 0),
                redis_vip=redis_vip,
                redis_premium=redis_premium,
                redis_standard=redis_standard
            )
        )

    @strawberry.field
    def event_waitlist_analytics(
        self,
        event_id: strawberry.ID,
        use_cache: bool = True,
        info: Info = None
    ) -> EventWaitlistAnalyticsType:
        """
        [ADMIN] Get comprehensive waitlist analytics for an event.

        Requires admin or organizer authorization.
        """
        user = info.context.user
        if not user:
            raise HTTPException(status_code=401, detail="Authentication required")

        db = info.context.db
        event_id_str = str(event_id)

        # Authorization check
        from ..models.event import Event as EventModel

        event = db.query(EventModel).filter(EventModel.id == event_id_str).first()
        if not event:
            raise HTTPException(status_code=404, detail="Event not found")

        user_id = user.get("sub")
        user_org_id = user.get("orgId")

        if event.owner_id != user_id and (not user_org_id or event.organization_id != user_org_id):
            raise HTTPException(status_code=403, detail="Not authorized")

        # Get analytics
        metrics = get_event_analytics(db, event_id_str, use_cache=use_cache)

        # Get cache timestamp
        cached_at = None
        if use_cache:
            first_metric = waitlist_analytics_crud.get_metric(
                db,
                event_id_str,
                'total_waitlist_entries'
            )
            if first_metric:
                cached_at = first_metric.calculated_at.isoformat()

        return EventWaitlistAnalyticsType(
            event_id=event_id_str,
            cached_at=cached_at,
            **metrics
        )
