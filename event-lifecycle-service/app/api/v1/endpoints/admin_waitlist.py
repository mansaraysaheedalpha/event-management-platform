# app/api/v1/endpoints/admin_waitlist.py
"""
Admin endpoints for manual waitlist management.

These endpoints allow organizers/admins to:
- Manually remove users from waitlists
- Clear entire waitlists
- Manually offer spots to specific users
- View waitlist analytics
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Request, BackgroundTasks
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
    get_total_waiting,
    get_next_in_queue
)
from app.utils.validators import validate_session_id, validate_user_id
from pydantic import BaseModel, Field
from app.utils.waitlist_notifications import send_waitlist_offer_notification, offer_spot_to_next_user

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


class BulkSendOffersRequest(BaseModel):
    """Request to bulk send offers"""
    count: int = Field(..., ge=1, le=100, description="Number of offers to send (1-100)")
    expires_minutes: int = Field(default=5, ge=1, le=60, description="Offer expiry in minutes")


class BulkSendOffersResponse(BaseModel):
    """Response for bulk send offers"""
    success: bool
    offers_sent: int
    message: str


class UpdateCapacityRequest(BaseModel):
    """Request to update session capacity"""
    capacity: int = Field(..., ge=0, description="New maximum capacity")


class UpdateCapacityResponse(BaseModel):
    """Response for capacity update"""
    session_id: str
    maximum_capacity: int
    current_attendance: int
    available_spots: int
    is_available: bool
    offers_automatically_sent: int = Field(default=0, description="Number of offers auto-sent if capacity increased")


class EventAnalyticsResponse(BaseModel):
    """Comprehensive event waitlist analytics"""
    event_id: str
    total_waitlist_entries: float
    active_waitlist_count: float
    total_offers_issued: float
    total_offers_accepted: float
    total_offers_declined: float
    total_offers_expired: float
    acceptance_rate: float
    decline_rate: float
    expiry_rate: float
    conversion_rate: float
    average_wait_time_minutes: float
    cached_at: Optional[str] = None


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
    background_tasks: BackgroundTasks,
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

    # M-CQ2: Offer spot to next person in line (shared helper)
    next_offered = offer_spot_to_next_user(
        session_id, redis_client, db, background_tasks,
        trigger_metadata={'triggered_by_admin_remove': True},
    )
    if next_offered:
        logger.info(f"Auto-offered spot to user {next_offered} after admin removed {user_id}")

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
    background_tasks: BackgroundTasks,
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

    # Send notification via background task
    from app.models.session import Session as SessionModel
    session_obj = db.query(SessionModel).filter(SessionModel.id == session_id).first()
    session_title = session_obj.title if session_obj else "Session"
    event_id = session_obj.event_id if session_obj else ""
    event_name = session_obj.event.name if (session_obj and session_obj.event) else "Event"

    background_tasks.add_task(
        send_waitlist_offer_notification,
        user_id=user_id,
        session_id=session_id,
        session_title=session_title,
        event_id=event_id,
        event_name=event_name,
        offer_token=offer_token,
        offer_expires_at=expires_at.isoformat(),
        position=entry.position,
    )

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
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(deps.get_db),
    current_user: TokenPayload = Depends(deps.get_current_user)
):
    """
    **[ADMIN]** List all waitlist entries for a session (paginated).

    **Authorization**: Requires admin or event organizer role

    **Query Parameters**:
    - status_filter: Filter by status (WAITING, OFFERED, etc.)
    - limit: Max entries to return (default 50, max 200)
    - offset: Number of entries to skip (default 0)

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

    # Clamp pagination params
    limit = max(1, min(limit, 200))
    offset = max(0, offset)

    # Build query with pagination
    query = db.query(session_waitlist.model).filter(
        session_waitlist.model.session_id == session_id
    )

    if status_filter:
        query = query.filter(session_waitlist.model.status == status_filter)

    entries = query.order_by(
        session_waitlist.model.priority_tier.desc(),
        session_waitlist.model.position.asc()
    ).offset(offset).limit(limit).all()

    return [WaitlistEntryResponse.from_orm(entry) for entry in entries]


@router.post(
    "/sessions/{session_id}/waitlist/bulk-send-offers",
    response_model=BulkSendOffersResponse
)
@limiter.limit("5/minute")
def admin_bulk_send_offers(
    session_id: str,
    request: Request,
    bulk_request: BulkSendOffersRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(deps.get_db),
    redis_client: redis.Redis = Depends(deps.get_redis),
    current_user: TokenPayload = Depends(deps.get_current_user)
):
    """
    **[ADMIN]** Bulk send waitlist offers to multiple users.

    **Authorization**: Requires admin or event organizer role

    **Process**:
    1. Check available spots
    2. Get top N waiting users (by priority)
    3. Generate offer tokens for each
    4. Update database statuses
    5. Log events
    6. Send notifications

    **Validation**:
    - Cannot send more offers than available spots
    - Only sends to users with WAITING status
    - Respects priority tiers (VIP → PREMIUM → STANDARD)

    **Use Cases**:
    - Capacity increase → send offers to multiple users
    - Batch processing after cancellations
    - Fast waitlist clearing

    **Errors**:
    - 400: Invalid session_id or count exceeds available spots
    - 403: Not authorized
    - 404: No waiting users found
    """
    # Validate ID
    validate_session_id(session_id)

    # Check authorization
    require_admin_or_organizer(current_user, session_id, db)

    # Check available capacity
    from app.crud.crud_session_capacity import session_capacity_crud
    capacity_obj = session_capacity_crud.get_or_create(db, session_id, default_capacity=100)
    available_spots = capacity_obj.maximum_capacity - capacity_obj.current_attendance

    if available_spots <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No available spots in session"
        )

    # Validate count
    count = min(bulk_request.count, available_spots)
    if count != bulk_request.count:
        logger.warning(
            f"Requested {bulk_request.count} offers but only {available_spots} spots available. "
            f"Sending {count} offers."
        )

    # Get waiting users by priority
    from app.utils.waitlist import get_next_in_queue
    offers_sent = 0
    user_ids_offered = []

    for _ in range(count):
        # Get next user in queue
        next_user_id, next_priority = get_next_in_queue(session_id, redis_client)

        if not next_user_id:
            logger.info(f"No more users in waitlist after sending {offers_sent} offers")
            break

        # Get user's waitlist entry
        entry = session_waitlist.get_active_entry(
            db,
            session_id=session_id,
            user_id=next_user_id
        )

        if not entry or entry.status != 'WAITING':
            logger.warning(f"User {next_user_id} not in WAITING status, skipping")
            continue

        # Generate offer token
        offer_token, expires_at = generate_offer_token(
            user_id=next_user_id,
            session_id=session_id,
            expires_minutes=bulk_request.expires_minutes
        )

        # Update entry with offer
        session_waitlist.set_offer(
            db,
            entry=entry,
            offer_token=offer_token,
            expires_at=expires_at
        )

        # Log event
        waitlist_event.log_event(
            db,
            waitlist_entry_id=entry.id,
            event_type='OFFERED',
            metadata={
                'offered_by': current_user.user_id,
                'bulk_offer': True,
                'expires_minutes': bulk_request.expires_minutes
            }
        )

        offers_sent += 1
        user_ids_offered.append(next_user_id)

        logger.info(f"Bulk offer sent to user {next_user_id} for session {session_id}")

    if offers_sent == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No users in waitlist with WAITING status"
        )

    # Send notifications for all offered users via background tasks
    from app.models.session import Session as SessionModel
    session_obj = db.query(SessionModel).filter(SessionModel.id == session_id).first()
    session_title = session_obj.title if session_obj else "Session"
    event_id_for_notif = session_obj.event_id if session_obj else ""
    event_name_for_notif = session_obj.event.name if (session_obj and session_obj.event) else "Event"

    # Re-fetch the offered entries to get their offer tokens and expiry times
    for offered_user_id in user_ids_offered:
        offered_entry = session_waitlist.get_by_session_and_user(
            db, session_id=session_id, user_id=offered_user_id
        )
        if offered_entry and offered_entry.offer_token and offered_entry.offer_expires_at:
            background_tasks.add_task(
                send_waitlist_offer_notification,
                user_id=offered_user_id,
                session_id=session_id,
                session_title=session_title,
                event_id=event_id_for_notif,
                event_name=event_name_for_notif,
                offer_token=offered_entry.offer_token,
                offer_expires_at=offered_entry.offer_expires_at.isoformat(),
                position=offered_entry.position,
            )

    logger.info(
        f"Admin {current_user.user_id} bulk sent {offers_sent} waitlist offers "
        f"for session {session_id}"
    )

    return BulkSendOffersResponse(
        success=True,
        offers_sent=offers_sent,
        message=f"Successfully sent {offers_sent} offers"
    )


@router.put(
    "/sessions/{session_id}/capacity",
    response_model=UpdateCapacityResponse
)
@limiter.limit("10/minute")
def admin_update_session_capacity(
    session_id: str,
    request: Request,
    capacity_request: UpdateCapacityRequest,
    db: Session = Depends(deps.get_db),
    redis_client: redis.Redis = Depends(deps.get_redis),
    current_user: TokenPayload = Depends(deps.get_current_user)
):
    """
    **[ADMIN]** Update session maximum capacity.

    **Authorization**: Requires admin or event organizer role

    **Process**:
    1. Validate new capacity >= current attendance
    2. Update capacity in database
    3. If capacity increased:
       - Calculate new available spots
       - Automatically send offers to waitlist (if any)

    **Automatic Offer Sending**:
    - If new_capacity > old_capacity:
      - new_spots = new_capacity - current_attendance
      - Send offers to top N users in waitlist

    **Use Cases**:
    - Venue upgrade (capacity increase)
    - Venue downgrade (capacity decrease)
    - Dynamic capacity management

    **Errors**:
    - 400: Invalid capacity (less than current attendance)
    - 403: Not authorized
    - 404: Session not found
    """
    # Validate ID
    validate_session_id(session_id)

    # Check authorization
    require_admin_or_organizer(current_user, session_id, db)

    # Get or create capacity entry
    from app.crud.crud_session_capacity import session_capacity_crud
    capacity_obj = session_capacity_crud.get_or_create(db, session_id, default_capacity=100)

    old_capacity = capacity_obj.maximum_capacity
    current_attendance = capacity_obj.current_attendance
    new_capacity = capacity_request.capacity

    # Validation: cannot set capacity below current attendance
    if new_capacity < current_attendance:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot set capacity ({new_capacity}) below current attendance ({current_attendance})"
        )

    # Update capacity
    updated_capacity = session_capacity_crud.update_maximum_capacity(
        db,
        session_id=session_id,
        new_capacity=new_capacity
    )

    if not updated_capacity:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update capacity"
        )

    # Calculate available spots
    available_spots = new_capacity - current_attendance

    # Automatic offer sending if capacity increased
    offers_auto_sent = 0
    if new_capacity > old_capacity and available_spots > 0:
        logger.info(
            f"Capacity increased from {old_capacity} to {new_capacity}. "
            f"Automatically sending {available_spots} offers."
        )

        # Get waiting users and send offers
        from app.utils.waitlist import get_next_in_queue

        for _ in range(available_spots):
            next_user_id, next_priority = get_next_in_queue(session_id, redis_client)

            if not next_user_id:
                logger.info(f"No more users in waitlist after auto-sending {offers_auto_sent} offers")
                break

            # Get user's waitlist entry
            entry = session_waitlist.get_active_entry(
                db,
                session_id=session_id,
                user_id=next_user_id
            )

            if not entry or entry.status != 'WAITING':
                continue

            # Generate offer token
            offer_token, expires_at = generate_offer_token(
                user_id=next_user_id,
                session_id=session_id,
                expires_minutes=5
            )

            # Update entry with offer
            session_waitlist.set_offer(
                db,
                entry=entry,
                offer_token=offer_token,
                expires_at=expires_at
            )

            # Log event
            waitlist_event.log_event(
                db,
                waitlist_entry_id=entry.id,
                event_type='OFFERED',
                metadata={
                    'offered_by': current_user.user_id,
                    'auto_offer_on_capacity_increase': True,
                    'old_capacity': old_capacity,
                    'new_capacity': new_capacity
                }
            )

            offers_auto_sent += 1

        logger.info(
            f"Automatically sent {offers_auto_sent} offers after capacity increase "
            f"for session {session_id}"
        )

    logger.info(
        f"Admin {current_user.user_id} updated capacity for session {session_id}: "
        f"{old_capacity} → {new_capacity}. Auto-sent {offers_auto_sent} offers."
    )

    return UpdateCapacityResponse(
        session_id=session_id,
        maximum_capacity=updated_capacity.maximum_capacity,
        current_attendance=updated_capacity.current_attendance,
        available_spots=available_spots,
        is_available=available_spots > 0,
        offers_automatically_sent=offers_auto_sent
    )


@router.get(
    "/events/{event_id}/waitlist/analytics",
    response_model=EventAnalyticsResponse
)
@limiter.limit("30/minute")
def admin_get_event_waitlist_analytics(
    event_id: str,
    request: Request,
    use_cache: bool = True,
    db: Session = Depends(deps.get_db),
    current_user: TokenPayload = Depends(deps.get_current_user)
):
    """
    **[ADMIN]** Get comprehensive waitlist analytics for an event.

    **Authorization**: Requires admin or event organizer role

    **Metrics Returned**:
    - Total waitlist entries across all sessions
    - Active waitlist count (currently waiting)
    - Total offers issued/accepted/declined/expired
    - Acceptance rate (% of offers accepted)
    - Decline rate (% of offers declined)
    - Expiry rate (% of offers expired)
    - Conversion rate (% of waiting users who got accepted)
    - Average wait time (from join to offer)

    **Query Parameters**:
    - use_cache: Use cached analytics if available (default: true)

    **Caching**:
    - Analytics are cached for 10 minutes
    - Set use_cache=false to force fresh calculation

    **Use Cases**:
    - Dashboard analytics
    - Event performance monitoring
    - Capacity planning
    - Waitlist optimization

    **Errors**:
    - 403: Not authorized
    - 404: Event not found
    """
    from app.utils.waitlist_analytics import get_event_analytics
    from app.models.event import Event as EventModel

    # Verify event exists
    event = db.query(EventModel).filter(EventModel.id == event_id).first()
    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Event not found"
        )

    # Check authorization
    user_id = current_user.sub
    user_org_id = current_user.org_id

    if event.owner_id != user_id and (not user_org_id or event.organization_id != user_org_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to view analytics for this event"
        )

    # Get analytics
    metrics = get_event_analytics(db, event_id, use_cache=use_cache)

    # Get cache timestamp if using cache
    cached_at = None
    if use_cache:
        from app.crud.crud_waitlist_analytics import waitlist_analytics_crud
        first_metric = waitlist_analytics_crud.get_metric(db, event_id, 'total_waitlist_entries')
        if first_metric:
            cached_at = first_metric.calculated_at.isoformat()

    return EventAnalyticsResponse(
        event_id=event_id,
        cached_at=cached_at,
        **metrics
    )
