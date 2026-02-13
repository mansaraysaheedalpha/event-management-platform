# app/utils/waitlist.py
"""
Waitlist utility functions for queue management and Redis operations.
"""

from typing import Optional
from datetime import datetime, timedelta, timezone
import redis
from sqlalchemy.orm import Session
from sqlalchemy import text
import jwt

from app.core.config import settings


def calculate_waitlist_position(
    session_id: str,
    user_id: str,
    priority_tier: str,
    redis_client: redis.Redis
) -> int:
    """
    Calculate user's position across all priority tiers using Redis pipeline.

    Falls back to DB-based position if Redis is unavailable.

    Logic:
    - VIP tier users are always ahead of PREMIUM/STANDARD
    - PREMIUM ahead of STANDARD
    - Within tier, ordered by join timestamp (Redis sorted set score)

    Args:
        session_id: Session ID
        user_id: User ID
        priority_tier: User's priority tier (VIP, PREMIUM, STANDARD)
        redis_client: Redis client instance

    Returns:
        Position in queue (1-indexed)
    """
    try:
        pipe = redis_client.pipeline()

        pipe.zcard(f"waitlist:session:{session_id}:vip")
        pipe.zcard(f"waitlist:session:{session_id}:premium")
        pipe.zcard(f"waitlist:session:{session_id}:standard")
        pipe.zrank(f"waitlist:session:{session_id}:{priority_tier.lower()}", user_id)

        vip_count, premium_count, standard_count, user_rank = pipe.execute()

        position = 0

        if priority_tier == 'PREMIUM':
            position += vip_count
        elif priority_tier == 'STANDARD':
            position += vip_count + premium_count

        if user_rank is not None:
            position += user_rank + 1

        return position

    except (redis.ConnectionError, redis.TimeoutError, redis.RedisError) as e:
        import logging
        logging.getLogger(__name__).warning(
            f"Redis unavailable for position calculation, falling back to DB: {e}"
        )
        return _calculate_position_from_db(session_id, user_id, priority_tier)


def get_total_waiting(session_id: str, redis_client: redis.Redis) -> int:
    """
    Get total number of users waiting across all tiers using Redis pipeline.

    Falls back to DB count if Redis is unavailable.

    Args:
        session_id: Session ID
        redis_client: Redis client instance

    Returns:
        Total number of users waiting
    """
    try:
        pipe = redis_client.pipeline()
        pipe.zcard(f"waitlist:session:{session_id}:vip")
        pipe.zcard(f"waitlist:session:{session_id}:premium")
        pipe.zcard(f"waitlist:session:{session_id}:standard")

        vip_count, premium_count, standard_count = pipe.execute()

        return vip_count + premium_count + standard_count

    except (redis.ConnectionError, redis.TimeoutError, redis.RedisError) as e:
        import logging
        logging.getLogger(__name__).warning(
            f"Redis unavailable for total waiting count, falling back to DB: {e}"
        )
        return _get_total_waiting_from_db(session_id)


def add_to_waitlist_queue(
    session_id: str,
    user_id: str,
    priority_tier: str,
    redis_client: redis.Redis,
    ttl_seconds: int = 86400  # 24 hours default TTL
) -> int:
    """
    Add user to Redis waitlist queue with TTL to prevent memory leaks.

    If Redis is unavailable, returns an approximate position from DB.

    Args:
        session_id: Session ID
        user_id: User ID
        priority_tier: Priority tier (VIP, PREMIUM, STANDARD)
        redis_client: Redis client instance
        ttl_seconds: Time-to-live for the queue in seconds (default: 24 hours)

    Returns:
        Position in queue after adding
    """
    try:
        timestamp = int(datetime.now(timezone.utc).timestamp() * 1000)

        queue_key = f"waitlist:session:{session_id}:{priority_tier.lower()}"

        redis_client.zadd(
            queue_key,
            {user_id: timestamp},
            nx=True
        )

        redis_client.expire(queue_key, ttl_seconds)

        return calculate_waitlist_position(session_id, user_id, priority_tier, redis_client)

    except (redis.ConnectionError, redis.TimeoutError, redis.RedisError) as e:
        import logging
        logging.getLogger(__name__).warning(
            f"Redis unavailable for waitlist add, returning DB-based position: {e}"
        )
        return _calculate_position_from_db(session_id, user_id, priority_tier)


def remove_from_waitlist_queue(
    session_id: str,
    user_id: str,
    priority_tier: str,
    redis_client: redis.Redis
) -> bool:
    """
    Remove user from Redis waitlist queue.

    Silently succeeds if Redis is unavailable (data will TTL out).

    Args:
        session_id: Session ID
        user_id: User ID
        priority_tier: Priority tier
        redis_client: Redis client instance

    Returns:
        True if user was removed, False if not in queue
    """
    try:
        removed = redis_client.zrem(
            f"waitlist:session:{session_id}:{priority_tier.lower()}",
            user_id
        )
        return removed > 0

    except (redis.ConnectionError, redis.TimeoutError, redis.RedisError) as e:
        import logging
        logging.getLogger(__name__).warning(
            f"Redis unavailable for waitlist remove (will TTL out): {e}"
        )
        return False


def get_next_in_queue(
    session_id: str,
    redis_client: redis.Redis
) -> Optional[tuple[str, str]]:
    """
    Get next user in queue (highest priority tier, oldest timestamp).

    Falls back to DB query if Redis is unavailable.
    Priority order: VIP → PREMIUM → STANDARD

    Args:
        session_id: Session ID
        redis_client: Redis client instance

    Returns:
        Tuple of (user_id, priority_tier) or None if queue is empty
    """
    try:
        for tier in ['vip', 'premium', 'standard']:
            users = redis_client.zrange(f"waitlist:session:{session_id}:{tier}", 0, 0)
            if users:
                user_id = users[0].decode() if isinstance(users[0], bytes) else users[0]
                return (user_id, tier.upper())
        return None

    except (redis.ConnectionError, redis.TimeoutError, redis.RedisError) as e:
        import logging
        logging.getLogger(__name__).warning(
            f"Redis unavailable for next-in-queue, falling back to DB: {e}"
        )
        return _get_next_in_queue_from_db(session_id)


def estimate_wait_time(session_id: str, position: int, db: Session) -> Optional[int]:
    """
    Estimate wait time in minutes based on historical data.

    Logic:
    - Calculate average time between acceptances for this session
    - Multiply by position
    - Round to nearest 5 minutes

    Args:
        session_id: Session ID
        position: Position in queue
        db: Database session

    Returns:
        Estimated wait time in minutes, or None if no historical data
    """
    # Query historical acceptance rate
    query = text("""
        SELECT AVG(
            EXTRACT(EPOCH FROM (offer_responded_at - offer_sent_at))
        ) as avg_seconds
        FROM session_waitlist
        WHERE session_id = :session_id
          AND status = 'ACCEPTED'
          AND offer_responded_at IS NOT NULL
        LIMIT 100
    """)

    result = db.execute(query, {"session_id": session_id}).fetchone()

    avg_time_between_acceptances = result[0] if result and result[0] else None

    if not avg_time_between_acceptances:
        # Default: assume 1 spot every 10 minutes
        avg_time_between_acceptances = 600

    estimated_seconds = position * avg_time_between_acceptances
    estimated_minutes = int(estimated_seconds / 60)

    # Round to nearest 5 minutes
    return round(estimated_minutes / 5) * 5


def generate_offer_token(
    user_id: str,
    session_id: str,
    expires_minutes: int = 5
) -> tuple[str, datetime]:
    """
    Generate short-lived JWT token for waitlist offer.

    Args:
        user_id: User ID
        session_id: Session ID
        expires_minutes: Token expiration in minutes (default: 5)

    Returns:
        Tuple of (token, expires_at datetime)
    """
    now = datetime.now(timezone.utc)  # ✅ Timezone-aware
    expires_at = now + timedelta(minutes=expires_minutes)

    token = jwt.encode(
        {
            'user_id': user_id,
            'session_id': session_id,
            'exp': expires_at,
            'iat': now
        },
        settings.JWT_SECRET,
        algorithm='HS256'
    )

    return token, expires_at


# ==================== DB Fallback Helpers ====================

def _calculate_position_from_db(session_id: str, user_id: str, priority_tier: str) -> int:
    """Fallback: calculate position from DB when Redis is unavailable."""
    from app.db.session import SessionLocal
    from app.models.session_waitlist import SessionWaitlist

    db = SessionLocal()
    try:
        entry = db.query(SessionWaitlist).filter(
            SessionWaitlist.session_id == session_id,
            SessionWaitlist.user_id == user_id,
            SessionWaitlist.status == 'WAITING'
        ).first()
        return entry.position if entry and entry.position else 1
    finally:
        db.close()


def _get_total_waiting_from_db(session_id: str) -> int:
    """Fallback: count waiting users from DB when Redis is unavailable."""
    from app.db.session import SessionLocal
    from app.models.session_waitlist import SessionWaitlist

    db = SessionLocal()
    try:
        return db.query(SessionWaitlist).filter(
            SessionWaitlist.session_id == session_id,
            SessionWaitlist.status == 'WAITING'
        ).count()
    finally:
        db.close()


def _get_next_in_queue_from_db(session_id: str) -> Optional[tuple[str, str]]:
    """Fallback: get next user from DB when Redis is unavailable."""
    from app.db.session import SessionLocal
    from app.models.session_waitlist import SessionWaitlist
    from sqlalchemy import case

    db = SessionLocal()
    try:
        # Order by priority tier (VIP first), then by position
        priority_order = case(
            (SessionWaitlist.priority_tier == 'VIP', 1),
            (SessionWaitlist.priority_tier == 'PREMIUM', 2),
            else_=3
        )
        entry = db.query(SessionWaitlist).filter(
            SessionWaitlist.session_id == session_id,
            SessionWaitlist.status == 'WAITING'
        ).order_by(priority_order, SessionWaitlist.position.asc()).first()

        if entry:
            return (entry.user_id, entry.priority_tier)
        return None
    finally:
        db.close()


def recalculate_all_positions(
    session_id: str,
    redis_client: redis.Redis,
    db
) -> int:
    """
    Recalculate positions for all users in a session's waitlist.

    Uses a Redis distributed lock to prevent concurrent recalculation races.
    This should be called after a user leaves to update everyone's position.

    Args:
        session_id: Session ID
        redis_client: Redis client
        db: Database session

    Returns:
        Number of entries updated
    """
    from app.crud.crud_session_waitlist import session_waitlist
    import logging
    _logger = logging.getLogger(__name__)

    # H2: Acquire a distributed lock to prevent concurrent recalculation
    lock_key = f"waitlist:recalc_lock:{session_id}"
    lock_acquired = False
    try:
        lock_acquired = redis_client.set(lock_key, "1", nx=True, ex=30)
    except (redis.ConnectionError, redis.TimeoutError, redis.RedisError):
        # If Redis is down, proceed without lock (best-effort)
        lock_acquired = True

    if not lock_acquired:
        _logger.debug(f"Skipping recalculation for session {session_id} - already in progress")
        return 0

    try:
        active_entries = session_waitlist.get_session_waitlist(
            db,
            session_id=session_id,
            status='WAITING'
        )

        updated_count = 0
        for entry in active_entries:
            new_position = calculate_waitlist_position(
                session_id=session_id,
                user_id=entry.user_id,
                priority_tier=entry.priority_tier,
                redis_client=redis_client
            )

            if entry.position != new_position:
                entry.position = new_position
                updated_count += 1

        if updated_count > 0:
            db.commit()

        return updated_count

    finally:
        # Release lock
        try:
            redis_client.delete(lock_key)
        except (redis.ConnectionError, redis.TimeoutError, redis.RedisError):
            pass


def verify_offer_token(token: str, user_id: str, session_id: str) -> bool:
    """
    Verify and decode waitlist offer token.

    Args:
        token: JWT token
        user_id: Expected user ID
        session_id: Expected session ID

    Returns:
        True if valid, False otherwise
    """
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=['HS256'])

        # Verify user_id and session_id match
        if payload.get('user_id') != user_id or payload.get('session_id') != session_id:
            return False

        return True

    except jwt.ExpiredSignatureError:
        return False
    except jwt.InvalidTokenError:
        return False



def get_user_ticket_tier(db, user_id: str, event_id: str) -> Optional[str]:
    """
    Look up the user's ticket type name for a given event.

    Queries the tickets table joined with ticket_types to find the user's
    highest-tier ticket for this event. Returns the ticket type name
    (e.g. 'VIP', 'Premium', 'General Admission') or None if no ticket found.

    Args:
        db: Database session
        user_id: User ID
        event_id: Event ID

    Returns:
        Ticket type name string, or None if no ticket found
    """
    try:
        from app.models.ticket import Ticket
        from app.models.ticket_type import TicketType

        # Find the user's valid ticket for this event, joined with ticket type
        ticket = db.query(Ticket).join(
            TicketType, Ticket.ticket_type_id == TicketType.id
        ).filter(
            Ticket.user_id == user_id,
            Ticket.event_id == event_id,
            Ticket.status.in_(['valid', 'checked_in'])
        ).first()

        if ticket and ticket.ticket_type:
            return ticket.ticket_type.name

        return None
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(
            f"Could not look up ticket tier for user {user_id}, event {event_id}: {e}"
        )
        return None


def map_ticket_to_priority(ticket_tier: Optional[str]) -> str:
    """
    Map ticket tier to waitlist priority tier.

    Logic:
    - VIP tickets → VIP priority
    - Premium/Gold tickets → PREMIUM priority
    - All others → STANDARD priority

    Args:
        ticket_tier: Ticket tier name

    Returns:
        Priority tier (VIP, PREMIUM, or STANDARD)
    """
    if not ticket_tier:
        return 'STANDARD'

    ticket_tier_upper = ticket_tier.upper()

    if 'VIP' in ticket_tier_upper:
        return 'VIP'
    elif any(keyword in ticket_tier_upper for keyword in ['PREMIUM', 'GOLD', 'PLATINUM']):
        return 'PREMIUM'
    else:
        return 'STANDARD'
