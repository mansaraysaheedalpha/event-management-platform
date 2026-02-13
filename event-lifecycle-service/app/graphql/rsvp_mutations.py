# app/graphql/rsvp_mutations.py
"""
GraphQL Mutation Resolvers for Session RSVP Management.

Provides mutation endpoints for:
- RSVP to a session (with capacity enforcement)
- Cancel session RSVP (with waitlist auto-offer)
"""

import strawberry
from strawberry.types import Info
from fastapi import HTTPException
import logging
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

from ..crud.crud_session_rsvp import session_rsvp as session_rsvp_crud
from ..crud.crud_session_capacity import session_capacity_crud
from ..utils.session_utils import require_event_registration
from ..utils.graphql_rate_limit import rate_limit
from ..constants.rsvp import RsvpStatus as RsvpStatusConstant
from .rsvp_types import (
    RsvpToSessionResponse,
    CancelSessionRsvpResponse,
    SessionRsvpType,
    RsvpToSessionInput,
    CancelSessionRsvpInput,
    RsvpStatus,
)

logger = logging.getLogger(__name__)


@strawberry.type
class RsvpMutations:
    """Session RSVP mutation resolvers."""

    @strawberry.mutation
    @rate_limit(max_calls=5, period_seconds=60)  # 5 RSVPs per minute per user
    def rsvp_to_session(
        self,
        input: RsvpToSessionInput,
        info: Info,
    ) -> RsvpToSessionResponse:
        """
        RSVP to a session.

        Requires authentication and event registration.
        Checks capacity before allowing RSVP.
        If session is full, returns error directing user to join waitlist.

        Rate limit: 5 requests per minute per user to prevent spam/abuse.
        """
        user = info.context.user
        if not user or not user.get("sub"):
            raise HTTPException(status_code=401, detail="Authentication required")

        user_id = user["sub"]
        db = info.context.db
        session_id = input.session_id

        # Verify session exists
        from ..models.session import Session as SessionModel
        session_obj = db.query(SessionModel).filter(SessionModel.id == session_id).first()
        if not session_obj:
            raise HTTPException(status_code=404, detail="Session not found")

        # Verify user is registered for the event
        require_event_registration(db, user_id, session_obj.event_id)

        # Check if already has an RSVP
        existing = session_rsvp_crud.get_user_rsvp(db, session_id=session_id, user_id=user_id)
        if existing and existing.status == RsvpStatusConstant.CONFIRMED:
            # Idempotent — return existing RSVP
            return RsvpToSessionResponse(
                success=True,
                rsvp=_to_rsvp_type(existing),
                message="Already RSVPed",
            )

        # Determine effective capacity (session model takes priority, fallback to capacity table)
        max_capacity = session_obj.max_participants
        if max_capacity is None:
            capacity_obj = session_capacity_crud.get_by_session(db, session_id)
            if capacity_obj:
                max_capacity = capacity_obj.maximum_capacity

        # Create or reactivate RSVP with atomic capacity check + capacity tracking
        # Both RSVP and capacity increment happen in same transaction (prevents data corruption)
        if existing and existing.status == RsvpStatusConstant.CANCELLED:
            rsvp, success = session_rsvp_crud.reactivate_rsvp_with_capacity_check(
                db,
                rsvp=existing,
                max_capacity=max_capacity,
                increment_capacity_tracking=True,  # Atomic increment
            )
        else:
            rsvp, success = session_rsvp_crud.create_rsvp_with_capacity_check(
                db,
                session_id=session_id,
                user_id=user_id,
                event_id=session_obj.event_id,
                max_capacity=max_capacity,
                increment_capacity_tracking=True,  # Atomic increment
            )

        if not success:
            return RsvpToSessionResponse(
                success=False,
                rsvp=None,
                message="Session is full. Join the waitlist for a chance to get a spot.",
            )

        # Capacity tracking already incremented atomically in CRUD method
        logger.info(f"User {user_id} RSVPed for session {session_id}")

        return RsvpToSessionResponse(
            success=True,
            rsvp=_to_rsvp_type(rsvp),
            message="Successfully RSVPed",
        )

    @strawberry.mutation
    @rate_limit(max_calls=5, period_seconds=60)  # 5 cancellations per minute per user
    def cancel_session_rsvp(
        self,
        input: CancelSessionRsvpInput,
        info: Info,
    ) -> CancelSessionRsvpResponse:
        """
        Cancel session RSVP.

        Requires authentication.
        Decrements capacity and auto-offers to next waitlist entry if applicable.

        Rate limit: 5 requests per minute per user to prevent RSVP/cancel spam.
        """
        user = info.context.user
        if not user or not user.get("sub"):
            raise HTTPException(status_code=401, detail="Authentication required")

        user_id = user["sub"]
        db = info.context.db
        session_id = input.session_id

        # Cancel RSVP with atomic capacity decrement
        # Both cancellation and capacity decrement happen in same transaction
        rsvp = session_rsvp_crud.cancel_rsvp(
            db,
            session_id=session_id,
            user_id=user_id,
            decrement_capacity_tracking=True,  # Atomic decrement
        )
        if not rsvp:
            raise HTTPException(status_code=404, detail="No active RSVP found for this session")

        # Capacity tracking already decremented atomically in CRUD method

        # Auto-offer to next person on waitlist (with retry for resilience)
        try:
            _auto_offer_next_waitlist_with_retry(db, session_id, info)
        except Exception as e:
            # Log critical failure after all retries exhausted
            logger.error(
                f"Failed to auto-offer waitlist spot for session {session_id} after retries: {e}",
                exc_info=True
            )
            # Don't fail the cancellation - spot will remain available for manual assignment

        logger.info(f"User {user_id} cancelled RSVP for session {session_id}")

        return CancelSessionRsvpResponse(
            success=True,
            message="RSVP cancelled successfully",
        )


def _to_rsvp_type(rsvp) -> SessionRsvpType:
    """Convert a SessionRsvp model instance to a SessionRsvpType."""
    return SessionRsvpType(
        id=rsvp.id,
        session_id=rsvp.session_id,
        user_id=rsvp.user_id,
        event_id=rsvp.event_id,
        status=RsvpStatus[rsvp.status],
        rsvp_at=rsvp.rsvp_at,
        cancelled_at=rsvp.cancelled_at,
    )


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type((ConnectionError, TimeoutError)),
    reraise=True,
)
def _auto_offer_next_waitlist_with_retry(db, session_id: str, info: Info) -> None:
    """
    Auto-offer to next waitlist entry with retry logic.

    Retries up to 3 times with exponential backoff for transient failures.
    Re-raises exception after all retries exhausted.
    """
    _auto_offer_next_waitlist(db, session_id, info)


def _auto_offer_next_waitlist(db, session_id: str, info: Info) -> None:
    """When an RSVP is cancelled, auto-offer to the next person on the waitlist."""
    try:
        from ..api.deps import get_redis
        from ..crud.crud_session_waitlist import session_waitlist, waitlist_event
        from ..utils.waitlist import (
            get_next_in_queue,
            generate_offer_token,
            recalculate_all_positions,
        )

        redis_client = next(get_redis())

        result = get_next_in_queue(session_id, redis_client)
        if not result:
            return
        next_user_id, next_priority = result

        next_entry = session_waitlist.get_active_entry(
            db, session_id=session_id, user_id=next_user_id
        )
        if next_entry and next_entry.status == 'WAITING':
            offer_token, expires_at = generate_offer_token(next_user_id, session_id, 5)
            session_waitlist.set_offer(
                db, entry=next_entry, offer_token=offer_token, expires_at=expires_at
            )
            waitlist_event.log_event(
                db,
                waitlist_entry_id=next_entry.id,
                event_type='OFFERED',
                metadata={'auto_offered_on_rsvp_cancel': True}
            )
            recalculate_all_positions(session_id, redis_client, db)
            logger.info(
                f"Auto-offered waitlist spot to user {next_user_id} "
                f"for session {session_id} after RSVP cancellation"
            )
    except Exception:
        # Waitlist auto-offer is best-effort; don't fail the cancellation
        logger.warning(f"Failed to auto-offer waitlist spot for session {session_id}", exc_info=True)
