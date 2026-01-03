# app/tasks/waitlist_tasks.py
"""
Background tasks for waitlist management.

These tasks should be run periodically (e.g., via cron jobs or scheduled tasks):
- check_expired_offers(): Every minute
- offer_spots_to_next_users(): Every 5 minutes
"""

import logging
from datetime import datetime, timezone
from typing import Optional
import redis

from app.db.session import SessionLocal
from app.crud.crud_session_waitlist import session_waitlist, waitlist_event
from app.utils.waitlist import (
    generate_offer_token,
    get_next_in_queue,
    remove_from_waitlist_queue
)
from app.core.config import settings

logger = logging.getLogger(__name__)


def get_redis_client() -> redis.Redis:
    """Get Redis client for background tasks"""
    from redis import ConnectionPool
    from app.api import deps

    return redis.Redis(connection_pool=deps.redis_pool)


def check_expired_offers():
    """
    Background task: Check for expired waitlist offers and mark them as EXPIRED.

    Should run every minute.

    Process:
    1. Find all offers where offer_expires_at < NOW() and status = 'OFFERED'
    2. Mark as EXPIRED
    3. Log event
    4. TODO: Notify user via Socket.io or email
    5. TODO: Offer spot to next person in line
    """
    db = SessionLocal()
    redis_client = get_redis_client()

    try:
        expired_offers = session_waitlist.get_expired_offers(db)

        for entry in expired_offers:
            # Mark as expired
            session_waitlist.update_status(db, entry=entry, status='EXPIRED')

            # Log event
            waitlist_event.log_event(
                db,
                waitlist_entry_id=entry.id,
                event_type='EXPIRED',
                metadata={
                    'offer_sent_at': entry.offer_sent_at.isoformat() if entry.offer_sent_at else None,
                    'offer_expires_at': entry.offer_expires_at.isoformat() if entry.offer_expires_at else None
                }
            )

            # Remove from Redis queue (if still there)
            remove_from_waitlist_queue(
                session_id=entry.session_id,
                user_id=entry.user_id,
                priority_tier=entry.priority_tier,
                redis_client=redis_client
            )

            logger.info(f"Marked waitlist offer as EXPIRED for user {entry.user_id}, session {entry.session_id}")

            # TODO: Send notification to user
            # TODO: Offer spot to next person in line

        if expired_offers:
            logger.info(f"Processed {len(expired_offers)} expired waitlist offers")

        return True

    except Exception as e:
        logger.error(f"Error checking expired offers: {e}")
        db.rollback()
        return False

    finally:
        db.close()
        redis_client.close()


def offer_spot_to_user(session_id: str, user_id: str, priority_tier: str):
    """
    Offer a waitlist spot to a specific user.

    Process:
    1. Generate JWT token (5 minute expiration)
    2. Update database with offer details
    3. Log event
    4. TODO: Send real-time notification via Socket.io
    5. TODO: Send email notification
    """
    db = SessionLocal()

    try:
        # Get user's waitlist entry
        entry = db.query(session_waitlist.model).filter(
            session_waitlist.model.session_id == session_id,
            session_waitlist.model.user_id == user_id,
            session_waitlist.model.status == 'WAITING'
        ).first()

        if not entry:
            logger.warning(f"No WAITING entry found for user {user_id}, session {session_id}")
            return False

        # Generate offer token
        token, expires_at = generate_offer_token(user_id, session_id, expires_minutes=5)

        # Update entry with offer details
        session_waitlist.set_offer(
            db,
            entry=entry,
            offer_token=token,
            expires_at=expires_at
        )

        # Log event
        waitlist_event.log_event(
            db,
            waitlist_entry_id=entry.id,
            event_type='OFFERED',
            metadata={
                'expires_at': expires_at.isoformat(),
                'priority_tier': priority_tier
            }
        )

        logger.info(f"Offered waitlist spot to user {user_id} for session {session_id}, expires at {expires_at}")

        # TODO: Send Socket.io event
        # await emit_waitlist_offer(user_id, session_id, token, expires_at)

        # TODO: Send email notification

        return True

    except Exception as e:
        logger.error(f"Error offering spot to user {user_id}: {e}")
        db.rollback()
        return False

    finally:
        db.close()


def offer_spots_to_next_users():
    """
    Background task: Check sessions and offer spots to next users in queue.

    Should run every 5 minutes.

    This is a simplified version. In production, this should be triggered by:
    - User leaving session
    - Session capacity increase
    - Offer expiration/decline

    For now, it checks all sessions with waiting users.
    """
    db = SessionLocal()
    redis_client = get_redis_client()

    try:
        # Get all unique session_ids with waiting users
        # This is a simplified approach - in production, use event-driven architecture
        waiting_sessions = db.query(
            session_waitlist.model.session_id
        ).filter(
            session_waitlist.model.status == 'WAITING'
        ).distinct().all()

        for (session_id,) in waiting_sessions:
            # Get next user in queue
            next_user = get_next_in_queue(session_id, redis_client)

            if next_user:
                user_id, priority_tier = next_user

                # Check if this user already has an active offer
                existing_offer = db.query(session_waitlist.model).filter(
                    session_waitlist.model.session_id == session_id,
                    session_waitlist.model.user_id == user_id,
                    session_waitlist.model.status == 'OFFERED'
                ).first()

                if not existing_offer:
                    # TODO: Check if session has capacity
                    # For now, we'll skip offering to avoid filling sessions unnecessarily
                    pass
                    # offer_spot_to_user(session_id, user_id, priority_tier)

        return True

    except Exception as e:
        logger.error(f"Error offering spots to next users: {e}")
        return False

    finally:
        db.close()
        redis_client.close()


# For testing/manual execution
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print("Running check_expired_offers...")
    check_expired_offers()
    print("Running offer_spots_to_next_users...")
    offer_spots_to_next_users()
