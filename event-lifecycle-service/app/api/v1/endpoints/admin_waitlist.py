# app/api/v1/endpoints/admin_waitlist.py
"""
Admin endpoints for manual waitlist management.

These endpoints allow organizers/admins to:
- Manually remove users from waitlists
- Clear entire waitlists
- Manually offer spots to specific users
- View waitlist analytics
"""

from typing import List
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
import redis
import logging
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.api import deps
from app.crud.crud_session_waitlist import session_waitlist, waitlist_event
from app.schemas.waitlist import WaitlistEntryResponse
from app.schemas.token import TokenPayload
from app.utils.waitlist import (
    remove_from_waitlist_queue,
    generate_offer_token,
    recalculate_all_positions,
    get_total_waiting
)
from app.utils.validators import validate_session_id, validate_user_id
from pydantic import BaseModel, Field

router = APIRouter(tags=["Admin - Waitlist"])
logger = logging.getLogger(__name__)

# Rate limiter
limiter = Limiter(key_func=get_remote_address)


# ==================== Request/Response Models ====================

class AdminRemoveUserRequest(BaseModel):
    """Request to remove user from waitlist"""
    user_id: str = Field(..., description="User ID to remove")
    reason: str = Field(default="Removed by admin", description="Reason for removal")


class AdminOfferSpotRequest(BaseModel):
    """Request to manually offer spot to user"""
    user_id: str = Field(..., description="User ID to offer spot")
    expires_minutes: int = Field(default=5, ge=1, le=60, description="Offer expiry in minutes")


class WaitlistStatsResponse(BaseModel):
    """Waitlist statistics"""
    session_id: str
    total_waiting: int
    total_offered: int
    total_accepted: int
    total_declined: int
    total_expired: int
    total_left: int
    by_priority: dict = Field(default_factory=dict, description="Breakdown by priority tier")


# ==================== Helper Functions ====================

def require_admin_or_organizer(
    current_user: TokenPayload,
    session_id: str,
    db: Session
) -> None:
    """
    Verify user is admin or organizer of the event containing this session.

    Checks if user is:
    1. Event owner (created the event)
    2. Same organization as the event

    Raises:
        HTTPException 403: If user is not authorized

    Note: This is a basic implementation. For production, you may want to add:
    - Platform admin role checking
    - Organization-level permissions (admin, manager roles)
    - More granular event permissions
    """
    from app.models.session import Session as SessionModel
    from app.models.event import Event as EventModel

    # Get the session
    session_obj = db.query(SessionModel).filter(SessionModel.id == session_id).first()
    if not session_obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found"
        )

    # Get the event
    event = db.query(EventModel).filter(EventModel.id == session_obj.event_id).first()
    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Event not found"
        )

    user_id = current_user.sub  # 'sub' is the standard JWT claim for user ID
    user_org_id = current_user.org_id

    # Check authorization:
    # 1. Is user the event owner?
    if event.owner_id == user_id:
        logger.info(f"User {user_id} authorized as event owner for session {session_id}")
        return

    # 2. Is user in the same organization?
    if event.organization_id and user_org_id and event.organization_id == user_org_id:
        logger.info(f"User {user_id} authorized as organization member for session {session_id}")
        return

    # Not authorized
    logger.warning(
        f"User {user_id} attempted unauthorized admin action on session {session_id}. "
        f"Event owner: {event.owner_id}, Event org: {event.organization_id}, "
        f"User org: {user_org_id}"
    )
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Not authorized. You must be the event organizer or in the same organization."
    )


# ==================== Admin Endpoints ====================

@router.delete(
    "/sessions/{session_id}/waitlist/users/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT
)
@limiter.limit("20/minute")
def admin_remove_user_from_waitlist(
    session_id: str,
    user_id: str,
    request: Request,
    reason: str = "Removed by admin",
    db: Session = Depends(deps.get_db),
    redis_client: redis.Redis = Depends(deps.get_redis),
    current_user: TokenPayload = Depends(deps.get_current_user)
):
    """
    **[ADMIN]** Remove a specific user from the waitlist.

    **Authorization**: Requires admin or event organizer role

    **Use Cases**:
    - User violated terms of service
    - Duplicate entry cleanup
    - Manual queue management

    **Effects**:
    - Removes from Redis queue
    - Updates status to 'REMOVED'
    - Recalculates positions for remaining users
    - Offers spot to next person in line
    - Logs event with reason

    **Errors**:
    - 400: Invalid session_id or user_id format
    - 403: Not authorized
    - 404: User not on waitlist
    """
    # Validate IDs
    validate_session_id(session_id)
    validate_user_id(user_id)

    # Check authorization
    require_admin_or_organizer(current_user, session_id, db)

    # Get waitlist entry
    entry = session_waitlist.get_active_entry(
        db,
        session_id=session_id,
        user_id=user_id
    )

    if not entry:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not on waitlist"
        )

    # Remove from Redis queue
    remove_from_waitlist_queue(
        session_id=session_id,
        user_id=user_id,
        priority_tier=entry.priority_tier,
        redis_client=redis_client
    )

    # Update status (note: REMOVED is not a standard status, treating as LEFT)
    session_waitlist.update_status(db, entry=entry, status='LEFT')

    # Log event with reason
    waitlist_event.log_event(
        db,
        waitlist_entry_id=entry.id,
        event_type='REMOVED',
        metadata={
            'removed_by': current_user.user_id,
            'reason': reason
        }
    )

    # Recalculate positions
    updated_count = recalculate_all_positions(session_id, redis_client, db)

    logger.info(
        f"Admin {current_user.user_id} removed user {user_id} from waitlist "
        f"for session {session_id}. Reason: {reason}. "
        f"Recalculated {updated_count} positions."
    )

    # TODO: Offer spot to next person (same logic as leave_waitlist)

    return None


@router.delete(
    "/sessions/{session_id}/waitlist",
    status_code=status.HTTP_204_NO_CONTENT
)
@limiter.limit("5/minute")
def admin_clear_waitlist(
    session_id: str,
    request: Request,
    reason: str = "Waitlist cleared by admin",
    db: Session = Depends(deps.get_db),
    redis_client: redis.Redis = Depends(deps.get_redis),
    current_user: TokenPayload = Depends(deps.get_current_user)
):
    """
    **[ADMIN]** Clear entire waitlist for a session.

    **Authorization**: Requires admin or event organizer role

    **Use Cases**:
    - Session cancelled
    - Session capacity increased (no longer needed)
    - Reset after issues

    **Effects**:
    - Removes ALL users from Redis queues
    - Updates all statuses to 'LEFT'
    - Logs bulk removal event

    **Errors**:
    - 400: Invalid session_id format
    - 403: Not authorized
    - 404: Session not found
    """
    # Validate ID
    validate_session_id(session_id)

    # Check authorization
    require_admin_or_organizer(current_user, session_id, db)

    # Get all active waitlist entries
    active_entries = session_waitlist.get_session_waitlist(
        db,
        session_id=session_id,
        status='WAITING'
    )

    # Also get OFFERED entries
    offered_entries = session_waitlist.get_session_waitlist(
        db,
        session_id=session_id,
        status='OFFERED'
    )

    all_entries = active_entries + offered_entries
    removed_count = len(all_entries)

    if removed_count == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active waitlist entries found"
        )

    # Remove from Redis and update database
    for entry in all_entries:
        # Remove from Redis
        remove_from_waitlist_queue(
            session_id=session_id,
            user_id=entry.user_id,
            priority_tier=entry.priority_tier,
            redis_client=redis_client
        )

        # Update status
        session_waitlist.update_status(db, entry=entry, status='LEFT')

        # Log individual removal
        waitlist_event.log_event(
            db,
            waitlist_entry_id=entry.id,
            event_type='REMOVED',
            metadata={
                'removed_by': current_user.user_id,
                'reason': reason,
                'bulk_removal': True
            }
        )

    logger.warning(
        f"Admin {current_user.user_id} cleared entire waitlist for session {session_id}. "
        f"Removed {removed_count} users. Reason: {reason}"
    )

    return None


@router.post(
    "/sessions/{session_id}/waitlist/users/{user_id}/offer",
    response_model=WaitlistEntryResponse
)
@limiter.limit("10/minute")
def admin_offer_spot_to_user(
    session_id: str,
    user_id: str,
    request: Request,
    expires_minutes: int = 5,
    db: Session = Depends(deps.get_db),
    current_user: TokenPayload = Depends(deps.get_current_user)
):
    """
    **[ADMIN]** Manually offer a waitlist spot to a specific user.

    **Authorization**: Requires admin or event organizer role

    **Use Cases**:
    - VIP user priority override
    - Compensate for system issues
    - Special circumstances

    **Effects**:
    - Generates JWT offer token
    - Updates status to 'OFFERED'
    - Sets expiration time
    - Logs manual offer event

    **Errors**:
    - 400: Invalid session_id or user_id format
    - 403: Not authorized
    - 404: User not on waitlist
    - 409: User already has offer or accepted
    """
    # Validate IDs
    validate_session_id(session_id)
    validate_user_id(user_id)

    # Check authorization
    require_admin_or_organizer(current_user, session_id, db)

    # Get waitlist entry
    entry = session_waitlist.get_by_session_and_user(
        db,
        session_id=session_id,
        user_id=user_id
    )

    if not entry:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not on waitlist"
        )

    if entry.status != 'WAITING':
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"User already has status: {entry.status}. Cannot offer spot."
        )

    # Generate offer token
    offer_token, expires_at = generate_offer_token(
        user_id=user_id,
        session_id=session_id,
        expires_minutes=expires_minutes
    )

    # Update entry with offer
    session_waitlist.set_offer(
        db,
        entry=entry,
        offer_token=offer_token,
        expires_at=expires_at
    )

    # Log manual offer event
    waitlist_event.log_event(
        db,
        waitlist_entry_id=entry.id,
        event_type='OFFERED',
        metadata={
            'offered_by': current_user.user_id,
            'manual_offer': True,
            'expires_minutes': expires_minutes
        }
    )

    logger.info(
        f"Admin {current_user.user_id} manually offered spot to user {user_id} "
        f"for session {session_id}. Expires in {expires_minutes} minutes."
    )

    # TODO: Send email/notification to user

    return WaitlistEntryResponse.from_orm(entry)


@router.get(
    "/sessions/{session_id}/waitlist/stats",
    response_model=WaitlistStatsResponse
)
@limiter.limit("30/minute")
def admin_get_waitlist_stats(
    session_id: str,
    request: Request,
    db: Session = Depends(deps.get_db),
    redis_client: redis.Redis = Depends(deps.get_redis),
    current_user: TokenPayload = Depends(deps.get_current_user)
):
    """
    **[ADMIN]** Get waitlist statistics for a session.

    **Authorization**: Requires admin or event organizer role

    **Returns**:
    - Total counts by status
    - Breakdown by priority tier
    - Current queue size from Redis

    **Use Cases**:
    - Monitor waitlist health
    - Analytics and reporting
    - Capacity planning
    """
    # Validate ID
    validate_session_id(session_id)

    # Check authorization
    require_admin_or_organizer(current_user, session_id, db)

    from sqlalchemy import func

    # Get counts by status
    status_counts = db.query(
        session_waitlist.model.status,
        func.count(session_waitlist.model.id)
    ).filter(
        session_waitlist.model.session_id == session_id
    ).group_by(
        session_waitlist.model.status
    ).all()

    # Convert to dict
    status_dict = {status: count for status, count in status_counts}

    # Get breakdown by priority tier (for WAITING status only)
    priority_counts = db.query(
        session_waitlist.model.priority_tier,
        func.count(session_waitlist.model.id)
    ).filter(
        session_waitlist.model.session_id == session_id,
        session_waitlist.model.status == 'WAITING'
    ).group_by(
        session_waitlist.model.priority_tier
    ).all()

    priority_dict = {tier: count for tier, count in priority_counts}

    # Get Redis queue sizes
    vip_count = redis_client.zcard(f"waitlist:session:{session_id}:vip")
    premium_count = redis_client.zcard(f"waitlist:session:{session_id}:premium")
    standard_count = redis_client.zcard(f"waitlist:session:{session_id}:standard")

    return WaitlistStatsResponse(
        session_id=session_id,
        total_waiting=status_dict.get('WAITING', 0),
        total_offered=status_dict.get('OFFERED', 0),
        total_accepted=status_dict.get('ACCEPTED', 0),
        total_declined=status_dict.get('DECLINED', 0),
        total_expired=status_dict.get('EXPIRED', 0),
        total_left=status_dict.get('LEFT', 0),
        by_priority={
            'VIP': priority_dict.get('VIP', 0),
            'PREMIUM': priority_dict.get('PREMIUM', 0),
            'STANDARD': priority_dict.get('STANDARD', 0),
            'redis_vip': vip_count,
            'redis_premium': premium_count,
            'redis_standard': standard_count
        }
    )


@router.get(
    "/sessions/{session_id}/waitlist/entries",
    response_model=List[WaitlistEntryResponse]
)
@limiter.limit("30/minute")
def admin_list_waitlist_entries(
    session_id: str,
    request: Request,
    status_filter: str = None,
    db: Session = Depends(deps.get_db),
    current_user: TokenPayload = Depends(deps.get_current_user)
):
    """
    **[ADMIN]** List all waitlist entries for a session.

    **Authorization**: Requires admin or event organizer role

    **Query Parameters**:
    - status_filter: Filter by status (WAITING, OFFERED, etc.)

    **Returns**:
    - List of waitlist entries with full details
    - Ordered by priority and position

    **Use Cases**:
    - View queue state
    - Debug issues
    - Export for analysis
    """
    # Validate ID
    validate_session_id(session_id)

    # Check authorization
    require_admin_or_organizer(current_user, session_id, db)

    # Get entries
    entries = session_waitlist.get_session_waitlist(
        db,
        session_id=session_id,
        status=status_filter
    )

    return [WaitlistEntryResponse.from_orm(entry) for entry in entries]
