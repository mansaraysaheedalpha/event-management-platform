# app/utils/waitlist_notifications.py
"""
Shared notification helper for waitlist offer events.

This module provides a synchronous function designed to be called from
FastAPI BackgroundTasks. It fetches user info (async) and publishes a
Kafka event without blocking the main request worker thread.
"""
import asyncio
import logging
from typing import Optional

logger = logging.getLogger(__name__)


def send_waitlist_offer_notification(
    user_id: str,
    session_id: str,
    session_title: str,
    event_id: str,
    event_name: str,
    offer_token: str,
    offer_expires_at: str,
    position: Optional[int] = None,
) -> None:
    """
    Background task: fetch user email/name via user service and publish
    a Kafka WAITLIST_OFFER event for the email consumer.

    Safe to call from a BackgroundTasks context (runs in a threadpool thread
    where no event loop is running), so asyncio.run() is appropriate here
    unlike inside a sync endpoint handler running under uvicorn.
    """
    try:
        from app.utils.kafka_helpers import publish_waitlist_offer_event
        from app.utils.user_service import get_user_email, get_user_name

        # Run the async user-service calls in a fresh event loop.
        # BackgroundTasks run in a threadpool thread (no running loop),
        # so asyncio.run() is safe here.
        try:
            user_email = asyncio.run(get_user_email(user_id))
            user_name = asyncio.run(get_user_name(user_id))
        except Exception as e:
            logger.warning(f"Could not fetch user info for {user_id}: {e}. Using fallback values.")
            user_email = None
            user_name = "User"

        if user_email:
            publish_waitlist_offer_event(
                user_id=user_id,
                user_email=user_email,
                user_name=user_name,
                session_id=session_id,
                session_title=session_title,
                event_id=event_id,
                event_name=event_name,
                offer_token=offer_token,
                offer_expires_at=offer_expires_at,
                position=position,
            )
            logger.info(f"Published waitlist offer event for user {user_id}")
        else:
            logger.warning(
                f"No email available for user {user_id}. "
                f"Offer created but notification not sent."
            )
    except Exception as e:
        logger.error(
            f"Failed to send waitlist offer notification for user {user_id}: {e}",
            exc_info=True
        )


def offer_spot_to_next_user(
    session_id: str,
    redis_client,
    db,
    background_tasks,
    trigger_metadata: Optional[dict] = None,
) -> Optional[str]:
    """
    M-CQ2: Shared helper that offers a waitlist spot to the next user in queue.

    Consolidates the duplicated "offer next user" pattern from:
      - waitlist.py leave_waitlist
      - admin_waitlist.py admin_remove_from_waitlist

    Returns the user_id that was offered, or None if no eligible user.
    """
    from app.utils.waitlist import get_next_in_queue
    from app.crud.crud_session_waitlist import session_waitlist
    from app.crud.crud_waitlist_event import waitlist_event
    from app.utils.waitlist import generate_offer_token

    next_user_id, next_priority = get_next_in_queue(session_id, redis_client)
    if not next_user_id:
        return None

    next_entry = session_waitlist.get_active_entry(
        db, session_id=session_id, user_id=next_user_id
    )
    if not next_entry or next_entry.status != 'WAITING':
        return None

    offer_token, expires_at = generate_offer_token(
        user_id=next_user_id,
        session_id=session_id,
        expires_minutes=5,
    )

    session_waitlist.set_offer(
        db, entry=next_entry,
        offer_token=offer_token, expires_at=expires_at,
    )

    event_meta = {'auto_offered': True}
    if trigger_metadata:
        event_meta.update(trigger_metadata)

    waitlist_event.log_event(
        db,
        waitlist_entry_id=next_entry.id,
        event_type='OFFERED',
        metadata=event_meta,
    )

    # Fetch session context for notification
    from app.models.session import Session as SessionModel
    session_obj = db.query(SessionModel).filter(SessionModel.id == session_id).first()
    session_title = session_obj.title if session_obj else "Session"
    event_id = session_obj.event_id if session_obj else ""
    event_name = session_obj.event.name if (session_obj and session_obj.event) else "Event"

    background_tasks.add_task(
        send_waitlist_offer_notification,
        user_id=next_user_id,
        session_id=session_id,
        session_title=session_title,
        event_id=event_id,
        event_name=event_name,
        offer_token=offer_token,
        offer_expires_at=expires_at.isoformat(),
        position=next_entry.position,
    )

    return next_user_id
