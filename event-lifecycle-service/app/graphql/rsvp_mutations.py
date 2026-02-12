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

from ..crud.crud_session_rsvp import session_rsvp as session_rsvp_crud
from ..crud.crud_session_capacity import session_capacity_crud
from ..utils.session_utils import require_event_registration
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
        """
        user = info.context.user
        if not user:
            raise HTTPException(status_code=401, detail="Authentication required")

        user_id = user.get("sub")
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
        if existing:
            if existing.status == "CONFIRMED":
                # Idempotent — return existing RSVP
                return RsvpToSessionResponse(
                    success=True,
                    rsvp=_to_rsvp_type(existing),
                    message="Already RSVPed",
                )
            else:
                # Previously cancelled — reactivate if capacity allows
                pass  # Fall through to capacity check below, will reactivate

        # Determine effective capacity (session model takes priority, fallback to capacity table)
        max_capacity = session_obj.max_participants
        if max_capacity is None:
            capacity_obj = session_capacity_crud.get_by_session(db, session_id)
            if capacity_obj:
                max_capacity = capacity_obj.maximum_capacity

        # Check capacity if a limit exists
        if max_capacity is not None:
            rsvp_count = session_rsvp_crud.get_rsvp_count(db, session_id=session_id)
            if rsvp_count >= max_capacity:
                return RsvpToSessionResponse(
                    success=False,
                    rsvp=None,
                    message="Session is full. Join the waitlist for a chance to get a spot.",
                )

        # Create or reactivate RSVP
        if existing and existing.status == "CANCELLED":
            rsvp = session_rsvp_crud.reactivate_rsvp(db, rsvp=existing)
        else:
            rsvp = session_rsvp_crud.create_rsvp(
                db,
                session_id=session_id,
                user_id=user_id,
                event_id=session_obj.event_id,
            )

        # Increment session_capacity tracking
        session_capacity_crud.increment_attendance(db, session_id)

        logger.info(f"User {user_id} RSVPed for session {session_id}")

        return RsvpToSessionResponse(
            success=True,
            rsvp=_to_rsvp_type(rsvp),
            message="Successfully RSVPed",
        )

    @strawberry.mutation
    def cancel_session_rsvp(
        self,
        input: CancelSessionRsvpInput,
        info: Info,
    ) -> CancelSessionRsvpResponse:
        """
        Cancel session RSVP.

        Requires authentication.
        Decrements capacity and auto-offers to next waitlist entry if applicable.
        """
        user = info.context.user
        if not user:
            raise HTTPException(status_code=401, detail="Authentication required")

        user_id = user.get("sub")
        db = info.context.db
        session_id = input.session_id

        # Cancel the RSVP
        rsvp = session_rsvp_crud.cancel_rsvp(db, session_id=session_id, user_id=user_id)
        if not rsvp:
            raise HTTPException(status_code=404, detail="No active RSVP found for this session")

        # Decrement session_capacity tracking
        session_capacity_crud.decrement_attendance(db, session_id)

        # Auto-offer to next person on waitlist
        _auto_offer_next_waitlist(db, session_id, info)

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
    except Exception as e:
        # Waitlist auto-offer is best-effort; don't fail the cancellation
        logger.warning(f"Failed to auto-offer waitlist spot for session {session_id}: {e}")
