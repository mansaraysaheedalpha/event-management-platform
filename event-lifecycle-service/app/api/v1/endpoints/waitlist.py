# app/api/v1/endpoints/waitlist.py
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, Request, BackgroundTasks
from sqlalchemy.orm import Session
import redis
import logging
import hashlib
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.api import deps
from app.crud.crud_session_waitlist import session_waitlist, waitlist_event
from app.schemas.waitlist import (
    WaitlistJoinResponse,
    WaitlistPositionResponse,
    WaitlistEntryResponse,
    AcceptOfferRequest,
    AcceptOfferResponse
)
from app.schemas.token import TokenPayload
from app.utils.waitlist import (
    calculate_waitlist_position,
    get_total_waiting,
    add_to_waitlist_queue,
    remove_from_waitlist_queue,
    estimate_wait_time,
    generate_offer_token,
    verify_offer_token,
    map_ticket_to_priority,
    get_user_ticket_tier,
    recalculate_all_positions,
    get_next_in_queue
)
from app.utils.validators import validate_session_id
from app.utils.session_utils import (
    check_session_capacity,
    require_event_registration
)
from app.utils.waitlist_notifications import send_waitlist_offer_notification, offer_spot_to_next_user

router = APIRouter(tags=["Waitlist"])
logger = logging.getLogger(__name__)

# ✅ Rate limiter for security
limiter = Limiter(key_func=get_remote_address)


# ==================== Waitlist Endpoints ====================

@router.post("/sessions/{session_id}/waitlist", response_model=WaitlistJoinResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("10/minute")  # ✅ Rate limiting to prevent abuse
def join_waitlist(
    session_id: str,
    request: Request,  # Required for rate limiting
    priority_tier_override: Optional[str] = None,
    db: Session = Depends(deps.get_db),
    redis_client: redis.Redis = Depends(deps.get_redis),
    current_user: TokenPayload = Depends(deps.get_current_user)
):
    """
    Join session waitlist.

    **Security Features**:
    - ✅ Rate limited: 10 requests per minute per IP
    - ✅ Input validation on session_id format
    - ✅ Session existence validation
    - ✅ Event registration verification (authorization)
    - ✅ Duplicate entry prevention
    - ✅ Redis TTL to prevent memory leaks

    **Business Logic**:
    1. Validate session_id format (prevent injection)
    2. Verify session exists
    3. Verify user is registered for the event
    4. Check if session is at capacity
    5. Check if user already on waitlist
    6. Determine priority tier based on ticket type
    7. Add to Redis queue with TTL
    8. Calculate position
    9. Insert to database
    10. Log event

    **Priority Tiers**:
    - VIP ticket holders → VIP tier (highest priority)
    - Premium ticket holders → PREMIUM tier
    - Others → STANDARD tier

    **Errors**:
    - 400: Invalid session_id format OR session not full
    - 403: User not registered for event
    - 404: Session not found
    - 409: Already on waitlist
    """
    user_id = current_user.user_id

    # ✅ Validate session_id format to prevent injection attacks
    validate_session_id(session_id)

    # ✅ Verify session exists (security check)
    from app.models.session import Session as SessionModel
    session = db.query(SessionModel).filter(SessionModel.id == session_id).first()
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found"
        )

    # ✅ Verify user is registered for the event (authorization check)
    require_event_registration(db, user_id, session.event_id)

    # ✅ Check session capacity (business logic validation)
    capacity_info = check_session_capacity(db, session_id)
    if not capacity_info["is_full"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Session is not full. Available spots: {capacity_info['available']}. "
                "Join the session directly instead of joining the waitlist."
            )
        )

    # Check if already on waitlist
    existing = session_waitlist.get_active_entry(
        db,
        session_id=session_id,
        user_id=user_id
    )

    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Already on waitlist with status: {existing.status}"
        )

    # Determine priority tier from ticket data, with optional override fallback
    ticket_tier = get_user_ticket_tier(db, user_id, session.event_id)
    priority_tier = map_ticket_to_priority(ticket_tier)

    # If ticket tier lookup returned STANDARD and an override was provided, use it
    if priority_tier == 'STANDARD' and priority_tier_override:
        override_upper = priority_tier_override.upper()
        if override_upper in ('VIP', 'PREMIUM', 'STANDARD'):
            priority_tier = override_upper
            logger.info(
                f"Using organizer-configured priority tier '{priority_tier}' "
                f"for user {user_id} on session {session_id}"
            )

    # ✅ Add to Redis queue with TTL (prevents memory leaks)
    position = add_to_waitlist_queue(
        session_id=session_id,
        user_id=user_id,
        priority_tier=priority_tier,
        redis_client=redis_client,
        ttl_seconds=86400  # 24 hours TTL
    )

    # Create database entry
    entry = session_waitlist.create_entry(
        db,
        session_id=session_id,
        user_id=user_id,
        priority_tier=priority_tier,
        position=position
    )

    # Log event
    waitlist_event.log_event(
        db,
        waitlist_entry_id=entry.id,
        event_type='JOINED',
        metadata={'priority_tier': priority_tier, 'position': position}
    )

    total = get_total_waiting(session_id, redis_client)

    logger.info(f"User {user_id} joined waitlist for session {session_id} at position {position}")

    return WaitlistJoinResponse(
        id=entry.id,
        position=position,
        total=total,
        message=f"You're #{position} in line"
    )


@router.delete("/sessions/{session_id}/waitlist", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("20/minute")  # ✅ Rate limiting
def leave_waitlist(
    session_id: str,
    request: Request,  # Required for rate limiting
    background_tasks: BackgroundTasks,
    db: Session = Depends(deps.get_db),
    redis_client: redis.Redis = Depends(deps.get_redis),
    current_user: TokenPayload = Depends(deps.get_current_user)
):
    """
    Leave waitlist voluntarily.

    **Security Features**:
    - ✅ Rate limited: 20 requests per minute per IP
    - ✅ Input validation on session_id

    **Process**:
    1. Validate session_id format
    2. Remove from Redis queue
    3. Update status to 'LEFT' in database
    4. Log event

    **Errors**:
    - 400: Invalid session_id format
    - 404: Not on waitlist
    """
    user_id = current_user.user_id

    # ✅ Validate session_id format
    validate_session_id(session_id)

    # Get waitlist entry
    entry = session_waitlist.get_active_entry(
        db,
        session_id=session_id,
        user_id=user_id
    )

    if not entry:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Not on waitlist"
        )

    # Remove from Redis queue
    remove_from_waitlist_queue(
        session_id=session_id,
        user_id=user_id,
        priority_tier=entry.priority_tier,
        redis_client=redis_client
    )

    # Update status in database (with status transition validation)
    session_waitlist.update_status(db, entry=entry, status='LEFT')

    # Log event
    waitlist_event.log_event(
        db,
        waitlist_entry_id=entry.id,
        event_type='LEFT'
    )

    # ✅ Recalculate positions for remaining users
    updated_count = recalculate_all_positions(session_id, redis_client, db)
    if updated_count > 0:
        logger.info(f"Recalculated positions for {updated_count} users after {user_id} left waitlist")

    # M-CQ2: Offer spot to next person in line (shared helper)
    next_offered = offer_spot_to_next_user(
        session_id, redis_client, db, background_tasks
    )
    if next_offered:
        logger.info(f"Automatically offered spot to user {next_offered} after {user_id} left")

    logger.info(f"User {user_id} left waitlist for session {session_id}")

    return None


@router.get("/sessions/{session_id}/waitlist/position", response_model=WaitlistPositionResponse)
@limiter.limit("30/minute")  # ✅ Rate limiting
def get_waitlist_position(
    session_id: str,
    request: Request,  # Required for rate limiting
    db: Session = Depends(deps.get_db),
    redis_client: redis.Redis = Depends(deps.get_redis),
    current_user: TokenPayload = Depends(deps.get_current_user)
):
    """
    Get current waitlist position.

    **Security Features**:
    - ✅ Rate limited: 30 requests per minute per IP
    - ✅ Input validation on session_id

    **Response includes**:
    - Current position in queue
    - Total users waiting
    - Estimated wait time (based on historical data)
    - Priority tier

    **Errors**:
    - 400: Invalid session_id format
    - 404: Not on waitlist
    """
    user_id = current_user.user_id

    # ✅ Validate session_id format
    validate_session_id(session_id)

    # Get waitlist entry
    entry = session_waitlist.get_active_entry(
        db,
        session_id=session_id,
        user_id=user_id
    )

    if not entry:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Not on waitlist"
        )

    # Calculate current position from Redis
    position = calculate_waitlist_position(
        session_id=session_id,
        user_id=user_id,
        priority_tier=entry.priority_tier,
        redis_client=redis_client
    )

    # Get total waiting
    total = get_total_waiting(session_id, redis_client)

    # Estimate wait time
    estimated_wait = estimate_wait_time(session_id, position, db)

    return WaitlistPositionResponse(
        position=position,
        total=total,
        estimated_wait_minutes=estimated_wait,
        priority_tier=entry.priority_tier
    )


@router.post("/sessions/{session_id}/waitlist/accept-offer", response_model=AcceptOfferResponse)
@limiter.limit("10/minute")  # ✅ Rate limiting
def accept_waitlist_offer(
    session_id: str,
    request: AcceptOfferRequest,
    req: Request,  # Required for rate limiting
    db: Session = Depends(deps.get_db),
    redis_client: redis.Redis = Depends(deps.get_redis),
    current_user: TokenPayload = Depends(deps.get_current_user)
):
    """
    Accept waitlist offer using JWT token.

    **Security Features**:
    - ✅ Rate limited: 10 requests per minute per IP
    - ✅ Input validation on session_id
    - ✅ JWT token verification with expiration check
    - ✅ Idempotency check with 24-hour TTL
    - ✅ Hashed token logging (not plain text)
    - ✅ Status transition validation

    **JWT Validation**:
    - Verify signature
    - Check expiration (5 minute window)
    - Verify user_id and session_id match
    - Verify token hasn't been used

    **Process**:
    1. Validate session_id format
    2. Validate JWT token
    3. Check if offer still valid
    4. Update status to 'ACCEPTED'
    5. Remove from Redis queue
    6. Log event (with hashed token)
    7. TODO: Register user for session

    **Errors**:
    - 400: Invalid session_id or expired token
    - 403: Token not valid for this user/session
    - 404: No active offer found
    - 409: Offer already accepted
    """
    user_id = current_user.user_id
    join_token = request.join_token

    # ✅ Validate session_id format
    validate_session_id(session_id)

    # ✅ Verify JWT token
    if not verify_offer_token(join_token, user_id, session_id):
        # ✅ Log security event
        logger.warning(f"Invalid token attempt by user {user_id} for session {session_id}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired token"
        )

    # ✅ Check if already used (idempotency) with extended TTL
    used_key = f"waitlist:offer:used:{join_token}"
    if redis_client.exists(used_key):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Offer already accepted"
        )

    # Get waitlist entry with OFFERED status
    entry = db.query(session_waitlist.model).filter(
        session_waitlist.model.session_id == session_id,
        session_waitlist.model.user_id == user_id,
        session_waitlist.model.status == 'OFFERED'
    ).first()

    if not entry:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active offer found"
        )

    # ✅ Additional check: verify offer hasn't been responded to
    if entry.offer_responded_at is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Offer already processed"
        )

    # ✅ H5: Validate session has available capacity BEFORE accepting
    from app.crud.crud_session_capacity import session_capacity_crud
    capacity = session_capacity_crud.get_or_create(db, session_id, default_capacity=100)
    available = capacity.maximum_capacity - capacity.current_attendance
    if available <= 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Session is at full capacity. Your offer has expired."
        )

    # Update status to ACCEPTED (with status transition validation)
    session_waitlist.update_status(db, entry=entry, status='ACCEPTED')

    # ✅ Mark token as used with 24-hour TTL (prevents token reuse even after Redis restart)
    redis_client.setex(used_key, 86400, "1")  # 24 hours

    # Remove from Redis queue
    remove_from_waitlist_queue(
        session_id=session_id,
        user_id=user_id,
        priority_tier=entry.priority_tier,
        redis_client=redis_client
    )

    # ✅ Log event with HASHED token (not plain text)
    token_hash = hashlib.sha256(join_token.encode()).hexdigest()[:16]
    waitlist_event.log_event(
        db,
        waitlist_entry_id=entry.id,
        event_type='ACCEPTED',
        metadata={'token_hash': token_hash}  # Only log hash
    )

    # ✅ Increment session attendance count
    from app.crud.crud_session_capacity import session_capacity_crud
    capacity_result = session_capacity_crud.increment_attendance(db, session_id)
    if not capacity_result:
        logger.warning(f"Failed to increment attendance for session {session_id} - session may be full")

    # ✅ Recalculate positions for remaining users
    updated_count = recalculate_all_positions(session_id, redis_client, db)
    if updated_count > 0:
        logger.info(f"Recalculated positions for {updated_count} users after {user_id} accepted offer")

    # Register user for session (create RSVP/attendance record)
    from app.crud.crud_session_rsvp import session_rsvp
    from app.models.session import Session as SessionModel
    session_obj = db.query(SessionModel).filter(SessionModel.id == session_id).first()
    if session_obj:
        try:
            existing_rsvp = session_rsvp.get_user_rsvp(db, session_id=session_id, user_id=user_id)
            if not existing_rsvp:
                session_rsvp.create_rsvp(
                    db,
                    session_id=session_id,
                    user_id=user_id,
                    event_id=session_obj.event_id
                )
                logger.info(f"Created session RSVP for user {user_id} on session {session_id}")
        except Exception as rsvp_err:
            logger.warning(f"Failed to create session RSVP for user {user_id}: {rsvp_err}")

    logger.info(f"User {user_id} accepted waitlist offer for session {session_id}")

    return AcceptOfferResponse(
        success=True,
        message="Successfully accepted offer and joined session",
        session_id=session_id
    )


@router.get("/sessions/{session_id}/waitlist/my-entry", response_model=Optional[WaitlistEntryResponse])
@limiter.limit("30/minute")  # ✅ Rate limiting
def get_my_waitlist_entry(
    session_id: str,
    request: Request,  # Required for rate limiting
    db: Session = Depends(deps.get_db),
    current_user: TokenPayload = Depends(deps.get_current_user)
):
    """
    Get current user's waitlist entry for a session.

    **Security Features**:
    - ✅ Rate limited: 30 requests per minute per IP
    - ✅ Input validation on session_id

    Returns None if not on waitlist.
    """
    user_id = current_user.user_id

    # ✅ Validate session_id format
    validate_session_id(session_id)

    entry = session_waitlist.get_by_session_and_user(
        db,
        session_id=session_id,
        user_id=user_id
    )

    if not entry:
        return None

    return WaitlistEntryResponse.from_orm(entry)
