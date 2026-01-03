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
    # ✅ Use Redis pipeline for batch operations (optimization)
    pipe = redis_client.pipeline()

    # Get counts for all tiers
    pipe.zcard(f"waitlist:session:{session_id}:vip")
    pipe.zcard(f"waitlist:session:{session_id}:premium")
    pipe.zcard(f"waitlist:session:{session_id}:standard")

    # Get user's rank in their tier
    pipe.zrank(f"waitlist:session:{session_id}:{priority_tier.lower()}", user_id)

    # Execute all commands at once
    vip_count, premium_count, standard_count, user_rank = pipe.execute()

    position = 0

    # Count all users in higher priority tiers
    if priority_tier == 'PREMIUM':
        position += vip_count
    elif priority_tier == 'STANDARD':
        position += vip_count + premium_count

    # Count users ahead in same tier
    if user_rank is not None:
        position += user_rank + 1  # zrank is 0-indexed

    return position


def get_total_waiting(session_id: str, redis_client: redis.Redis) -> int:
    """
    Get total number of users waiting across all tiers using Redis pipeline.

    Args:
        session_id: Session ID
        redis_client: Redis client instance

    Returns:
        Total number of users waiting
    """
    # ✅ Use Redis pipeline for batch operations (optimization)
    pipe = redis_client.pipeline()
    pipe.zcard(f"waitlist:session:{session_id}:vip")
    pipe.zcard(f"waitlist:session:{session_id}:premium")
    pipe.zcard(f"waitlist:session:{session_id}:standard")

    vip_count, premium_count, standard_count = pipe.execute()

    return vip_count + premium_count + standard_count


def add_to_waitlist_queue(
    session_id: str,
    user_id: str,
    priority_tier: str,
    redis_client: redis.Redis,
    ttl_seconds: int = 86400  # 24 hours default TTL
) -> int:
    """
    Add user to Redis waitlist queue with TTL to prevent memory leaks.

    Args:
        session_id: Session ID
        user_id: User ID
        priority_tier: Priority tier (VIP, PREMIUM, STANDARD)
        redis_client: Redis client instance
        ttl_seconds: Time-to-live for the queue in seconds (default: 24 hours)

    Returns:
        Position in queue after adding
    """
    # Use current timestamp (in milliseconds) as score for FIFO ordering within tier
    timestamp = int(datetime.now(timezone.utc).timestamp() * 1000)  # ✅ Timezone-aware

    queue_key = f"waitlist:session:{session_id}:{priority_tier.lower()}"

    # ✅ Use NX flag to prevent duplicate additions (idempotency check)
    added = redis_client.zadd(
        queue_key,
        {user_id: timestamp},
        nx=True  # Only add if not exists
    )

    # ✅ Set TTL to prevent memory leaks
    # This ensures the queue auto-expires after the session ends
    redis_client.expire(queue_key, ttl_seconds)

    return calculate_waitlist_position(session_id, user_id, priority_tier, redis_client)


def remove_from_waitlist_queue(
    session_id: str,
    user_id: str,
    priority_tier: str,
    redis_client: redis.Redis
) -> bool:
    """
    Remove user from Redis waitlist queue.

    Args:
        session_id: Session ID
        user_id: User ID
        priority_tier: Priority tier
        redis_client: Redis client instance

    Returns:
        True if user was removed, False if not in queue
    """
    removed = redis_client.zrem(
        f"waitlist:session:{session_id}:{priority_tier.lower()}",
        user_id
    )

    return removed > 0


def get_next_in_queue(
    session_id: str,
    redis_client: redis.Redis
) -> Optional[tuple[str, str]]:
    """
    Get next user in queue (highest priority tier, oldest timestamp).

    Priority order: VIP → PREMIUM → STANDARD

    Args:
        session_id: Session ID
        redis_client: Redis client instance

    Returns:
        Tuple of (user_id, priority_tier) or None if queue is empty
    """
    # Check VIP queue first
    vip_users = redis_client.zrange(f"waitlist:session:{session_id}:vip", 0, 0)
    if vip_users:
        return (vip_users[0].decode() if isinstance(vip_users[0], bytes) else vip_users[0], 'VIP')

    # Check PREMIUM queue
    premium_users = redis_client.zrange(f"waitlist:session:{session_id}:premium", 0, 0)
    if premium_users:
        return (premium_users[0].decode() if isinstance(premium_users[0], bytes) else premium_users[0], 'PREMIUM')

    # Check STANDARD queue
    standard_users = redis_client.zrange(f"waitlist:session:{session_id}:standard", 0, 0)
    if standard_users:
        return (standard_users[0].decode() if isinstance(standard_users[0], bytes) else standard_users[0], 'STANDARD')

    return None


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


def recalculate_all_positions(
    session_id: str,
    redis_client: redis.Redis,
    db
) -> int:
    """
    Recalculate positions for all users in a session's waitlist.

    This should be called after a user leaves to update everyone's position.

    Args:
        session_id: Session ID
        redis_client: Redis client
        db: Database session

    Returns:
        Number of entries updated
    """
    from app.crud.crud_session_waitlist import session_waitlist

    # Get all active waitlist entries for this session
    active_entries = session_waitlist.get_session_waitlist(
        db,
        session_id=session_id,
        status='WAITING'
    )

    updated_count = 0
    for entry in active_entries:
        # Recalculate position from Redis
        new_position = calculate_waitlist_position(
            session_id=session_id,
            user_id=entry.user_id,
            priority_tier=entry.priority_tier,
            redis_client=redis_client
        )

        # Update if position changed
        if entry.position != new_position:
            entry.position = new_position
            updated_count += 1

    if updated_count > 0:
        db.commit()

    return updated_count


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
