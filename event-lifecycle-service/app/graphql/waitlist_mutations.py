# app/graphql/waitlist_mutations.py
"""
GraphQL Mutation Resolvers for Waitlist Management.

Provides mutation endpoints for:
- Joining/leaving waitlist
- Accepting/declining offers
- Admin: removing users, sending offers, bulk operations
- Admin: updating session capacity
"""

import strawberry
from typing import Optional
from strawberry.types import Info
from fastapi import HTTPException
import redis
import logging

from .. import crud
from ..crud.crud_session_capacity import session_capacity_crud
from ..utils.waitlist import (
    add_to_waitlist_queue,
    remove_from_waitlist_queue,
    generate_offer_token,
    verify_offer_token,
    map_ticket_to_priority,
    recalculate_all_positions,
    get_next_in_queue,
    calculate_waitlist_position,
    get_total_waiting,
    estimate_wait_time
)
from ..utils.session_utils import check_session_capacity, require_event_registration
from ..utils.validators import validate_session_id, validate_user_id
from .waitlist_types import (
    WaitlistJoinResponseType,
    WaitlistLeaveResponseType,
    WaitlistAcceptOfferResponseType,
    BulkSendOffersResponseType,
    UpdateCapacityResponseType,
    WaitlistEntryType,
    JoinWaitlistInput,
    LeaveWaitlistInput,
    AcceptOfferInput,
    DeclineOfferInput,
    RemoveFromWaitlistInput,
    SendOfferInput,
    BulkSendOffersInput,
    UpdateCapacityInput,
    PriorityTier,
    WaitlistStatus
)

logger = logging.getLogger(__name__)


def _get_redis_client(info: Info) -> redis.Redis:
    """Get Redis client from dependency injection"""
    from ..api.deps import get_redis
    return next(get_redis())


def _check_organizer_permission(db, user, session_id: str) -> None:
    """Check if user is organizer of the event containing the session"""
    from ..models.session import Session as SessionModel
    from ..models.event import Event as EventModel

    session_obj = db.query(SessionModel).filter(SessionModel.id == session_id).first()
    if not session_obj:
        raise HTTPException(status_code=404, detail="Session not found")

    event = db.query(EventModel).filter(EventModel.id == session_obj.event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    user_id = user.get("sub")
    user_org_id = user.get("orgId")

    if event.owner_id != user_id and (not user_org_id or event.organization_id != user_org_id):
        raise HTTPException(
            status_code=403,
            detail="Not authorized. You must be the event organizer."
        )


@strawberry.type
class WaitlistMutations:
    """Waitlist mutation resolvers"""

    @strawberry.mutation
    def join_waitlist(
        self,
        input: JoinWaitlistInput,
        info: Info
    ) -> WaitlistJoinResponseType:
        """
        Join session waitlist.

        Requires authentication and event registration.
        """
        user = info.context.user
        if not user:
            raise HTTPException(status_code=401, detail="Authentication required")

        user_id = user.get("sub")
        db = info.context.db
        redis_client = _get_redis_client(info)
        session_id = input.session_id

        # Validate session ID
        validate_session_id(session_id)

        # Verify session exists
        from ..models.session import Session as SessionModel
        session = db.query(SessionModel).filter(SessionModel.id == session_id).first()
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")

        # Verify user is registered for the event
        require_event_registration(db, user_id, session.event_id)

        # Check if session is at capacity
        capacity_info = check_session_capacity(db, session_id)
        if not capacity_info["is_full"]:
            raise HTTPException(
                status_code=400,
                detail=f"Session has {capacity_info['available']} available spots. No need to join waitlist."
            )

        # Check if already on waitlist
        existing = crud.session_waitlist.get_active_entry(db, session_id=session_id, user_id=user_id)
        if existing:
            # Return existing entry
            position = calculate_waitlist_position(session_id, existing.priority_tier, existing.joined_at, db)
            estimated_wait = estimate_wait_time(session_id, position, db)

            return WaitlistJoinResponseType(
                id=existing.id,
                session_id=session_id,
                position=position,
                priority_tier=PriorityTier[existing.priority_tier],
                estimated_wait_minutes=estimated_wait,
                joined_at=existing.joined_at
            )

        # Determine priority tier based on ticket type
        # For now, default to STANDARD (can be enhanced with ticket type lookup)
        priority_tier = "STANDARD"

        # Add to Redis queue
        add_to_waitlist_queue(
            session_id=session_id,
            user_id=user_id,
            priority_tier=priority_tier,
            redis_client=redis_client
        )

        # Calculate position
        position = calculate_waitlist_position(
            session_id=session_id,
            priority_tier=priority_tier,
            joined_at=None,  # Will use current time
            db=db
        )

        # Create waitlist entry
        entry = crud.session_waitlist.create_entry(
            db,
            session_id=session_id,
            user_id=user_id,
            priority_tier=priority_tier,
            position=position
        )

        # Log event
        crud.waitlist_event.log_event(
            db,
            waitlist_entry_id=entry.id,
            event_type='JOINED'
        )

        # Estimate wait time
        estimated_wait = estimate_wait_time(session_id, position, db)

        logger.info(f"User {user_id} joined waitlist for session {session_id} at position {position}")

        return WaitlistJoinResponseType(
            id=entry.id,
            session_id=session_id,
            position=position,
            priority_tier=PriorityTier[priority_tier],
            estimated_wait_minutes=estimated_wait,
            joined_at=entry.joined_at
        )

    @strawberry.mutation
    def leave_waitlist(
        self,
        input: LeaveWaitlistInput,
        info: Info
    ) -> WaitlistLeaveResponseType:
        """
        Leave session waitlist.

        Requires authentication.
        """
        user = info.context.user
        if not user:
            raise HTTPException(status_code=401, detail="Authentication required")

        user_id = user.get("sub")
        db = info.context.db
        redis_client = _get_redis_client(info)
        session_id = input.session_id

        validate_session_id(session_id)

        # Get waitlist entry
        entry = crud.session_waitlist.get_active_entry(db, session_id=session_id, user_id=user_id)
        if not entry:
            raise HTTPException(status_code=404, detail="Not on waitlist")

        # Remove from Redis queue
        remove_from_waitlist_queue(
            session_id=session_id,
            user_id=user_id,
            priority_tier=entry.priority_tier,
            redis_client=redis_client
        )

        # Update status
        crud.session_waitlist.update_status(db, entry=entry, status='LEFT')

        # Log event
        crud.waitlist_event.log_event(db, waitlist_entry_id=entry.id, event_type='LEFT')

        # Recalculate positions
        recalculate_all_positions(session_id, redis_client, db)

        # Offer to next person
        next_user_id, next_priority = get_next_in_queue(session_id, redis_client)
        if next_user_id:
            next_entry = crud.session_waitlist.get_active_entry(db, session_id=session_id, user_id=next_user_id)
            if next_entry and next_entry.status == 'WAITING':
                offer_token, expires_at = generate_offer_token(next_user_id, session_id, 5)
                crud.session_waitlist.set_offer(db, entry=next_entry, offer_token=offer_token, expires_at=expires_at)
                crud.waitlist_event.log_event(
                    db,
                    waitlist_entry_id=next_entry.id,
                    event_type='OFFERED',
                    metadata={'auto_offered': True}
                )

        logger.info(f"User {user_id} left waitlist for session {session_id}")

        return WaitlistLeaveResponseType(
            success=True,
            message="Successfully left waitlist"
        )

    @strawberry.mutation
    def accept_waitlist_offer(
        self,
        input: AcceptOfferInput,
        info: Info
    ) -> WaitlistAcceptOfferResponseType:
        """
        Accept waitlist offer using JWT token.

        Requires authentication.
        """
        user = info.context.user
        if not user:
            raise HTTPException(status_code=401, detail="Authentication required")

        user_id = user.get("sub")
        db = info.context.db
        redis_client = _get_redis_client(info)
        session_id = input.session_id
        join_token = input.join_token

        validate_session_id(session_id)

        # Verify JWT token
        if not verify_offer_token(join_token, user_id, session_id):
            raise HTTPException(status_code=400, detail="Invalid or expired token")

        # Get waitlist entry
        entry = db.query(crud.session_waitlist.model).filter(
            crud.session_waitlist.model.session_id == session_id,
            crud.session_waitlist.model.user_id == user_id,
            crud.session_waitlist.model.status == 'OFFERED'
        ).first()

        if not entry:
            raise HTTPException(status_code=404, detail="No active offer found")

        if entry.offer_responded_at is not None:
            raise HTTPException(status_code=409, detail="Offer already processed")

        # Update status
        crud.session_waitlist.update_status(db, entry=entry, status='ACCEPTED')

        # Increment attendance
        capacity_result = session_capacity_crud.increment_attendance(db, session_id)
        if not capacity_result:
            logger.warning(f"Failed to increment attendance for session {session_id}")

        # Remove from Redis
        remove_from_waitlist_queue(session_id, user_id, entry.priority_tier, redis_client)

        # Log event
        crud.waitlist_event.log_event(db, waitlist_entry_id=entry.id, event_type='ACCEPTED')

        # Recalculate positions
        recalculate_all_positions(session_id, redis_client, db)

        logger.info(f"User {user_id} accepted waitlist offer for session {session_id}")

        return WaitlistAcceptOfferResponseType(
            success=True,
            message="Successfully accepted offer and joined session",
            session_id=session_id
        )

    @strawberry.mutation
    def decline_waitlist_offer(
        self,
        input: DeclineOfferInput,
        info: Info
    ) -> WaitlistLeaveResponseType:
        """
        Decline waitlist offer.

        User remains on waitlist for future offers.
        Requires authentication.
        """
        user = info.context.user
        if not user:
            raise HTTPException(status_code=401, detail="Authentication required")

        user_id = user.get("sub")
        db = info.context.db
        session_id = input.session_id

        validate_session_id(session_id)

        # Get entry
        entry = crud.session_waitlist.get_active_entry(db, session_id=session_id, user_id=user_id)
        if not entry:
            raise HTTPException(status_code=404, detail="Not on waitlist")

        # Update status
        crud.session_waitlist.update_status(db, entry=entry, status='DECLINED')

        # Log event
        crud.waitlist_event.log_event(db, waitlist_entry_id=entry.id, event_type='DECLINED')

        logger.info(f"User {user_id} declined waitlist offer for session {session_id}")

        return WaitlistLeaveResponseType(
            success=True,
            message="Offer declined. You remain on the waitlist."
        )

    @strawberry.mutation
    def remove_from_waitlist(
        self,
        input: RemoveFromWaitlistInput,
        info: Info
    ) -> WaitlistLeaveResponseType:
        """
        [ADMIN] Remove a user from waitlist.

        Requires admin or organizer authorization.
        """
        user = info.context.user
        if not user:
            raise HTTPException(status_code=401, detail="Authentication required")

        db = info.context.db
        redis_client = _get_redis_client(info)
        session_id = input.session_id
        target_user_id = input.user_id
        reason = input.reason or "Removed by admin"

        validate_session_id(session_id)
        validate_user_id(target_user_id)

        # Check authorization
        _check_organizer_permission(db, user, session_id)

        # Get entry
        entry = crud.session_waitlist.get_active_entry(db, session_id=session_id, user_id=target_user_id)
        if not entry:
            raise HTTPException(status_code=404, detail="User not on waitlist")

        # Remove from Redis
        remove_from_waitlist_queue(session_id, target_user_id, entry.priority_tier, redis_client)

        # Update status
        crud.session_waitlist.update_status(db, entry=entry, status='LEFT')

        # Log event
        crud.waitlist_event.log_event(
            db,
            waitlist_entry_id=entry.id,
            event_type='REMOVED',
            metadata={'removed_by': user.get("sub"), 'reason': reason}
        )

        # Recalculate positions
        recalculate_all_positions(session_id, redis_client, db)

        logger.info(f"Admin {user.get('sub')} removed user {target_user_id} from waitlist for session {session_id}")

        return WaitlistLeaveResponseType(
            success=True,
            message=f"User removed from waitlist. Reason: {reason}"
        )

    @strawberry.mutation
    def send_waitlist_offer(
        self,
        input: SendOfferInput,
        info: Info
    ) -> WaitlistEntryType:
        """
        [ADMIN] Manually send offer to a specific user.

        Requires admin or organizer authorization.
        """
        user = info.context.user
        if not user:
            raise HTTPException(status_code=401, detail="Authentication required")

        db = info.context.db
        session_id = input.session_id
        target_user_id = input.user_id
        expires_minutes = input.expires_minutes or 5

        validate_session_id(session_id)
        validate_user_id(target_user_id)

        # Check authorization
        _check_organizer_permission(db, user, session_id)

        # Get entry
        entry = crud.session_waitlist.get_by_session_and_user(db, session_id=session_id, user_id=target_user_id)
        if not entry:
            raise HTTPException(status_code=404, detail="User not on waitlist")

        if entry.status != 'WAITING':
            raise HTTPException(status_code=409, detail=f"User status is {entry.status}, cannot send offer")

        # Generate token
        offer_token, expires_at = generate_offer_token(target_user_id, session_id, expires_minutes)

        # Update entry
        crud.session_waitlist.set_offer(db, entry=entry, offer_token=offer_token, expires_at=expires_at)

        # Log event
        crud.waitlist_event.log_event(
            db,
            waitlist_entry_id=entry.id,
            event_type='OFFERED',
            metadata={'offered_by': user.get("sub"), 'manual_offer': True}
        )

        logger.info(f"Admin {user.get('sub')} sent offer to user {target_user_id} for session {session_id}")

        return WaitlistEntryType(
            id=entry.id,
            session_id=entry.session_id,
            user_id=entry.user_id,
            status=WaitlistStatus[entry.status],
            priority_tier=PriorityTier[entry.priority_tier],
            position=entry.position,
            joined_at=entry.joined_at,
            offer_sent_at=entry.offer_sent_at,
            offer_expires_at=entry.offer_expires_at,
            offer_responded_at=entry.offer_responded_at,
            left_at=entry.left_at
        )

    @strawberry.mutation
    def bulk_send_waitlist_offers(
        self,
        input: BulkSendOffersInput,
        info: Info
    ) -> BulkSendOffersResponseType:
        """
        [ADMIN] Bulk send offers to multiple users.

        Requires admin or organizer authorization.
        """
        user = info.context.user
        if not user:
            raise HTTPException(status_code=401, detail="Authentication required")

        db = info.context.db
        redis_client = _get_redis_client(info)
        session_id = input.session_id
        count = input.count
        expires_minutes = input.expires_minutes or 5

        validate_session_id(session_id)

        # Check authorization
        _check_organizer_permission(db, user, session_id)

        # Check capacity
        capacity_obj = session_capacity_crud.get_or_create(db, session_id, default_capacity=100)
        available_spots = capacity_obj.maximum_capacity - capacity_obj.current_attendance

        if available_spots <= 0:
            raise HTTPException(status_code=400, detail="No available spots in session")

        # Validate count
        actual_count = min(count, available_spots)

        offers_sent = 0
        for _ in range(actual_count):
            next_user_id, next_priority = get_next_in_queue(session_id, redis_client)
            if not next_user_id:
                break

            entry = crud.session_waitlist.get_active_entry(db, session_id=session_id, user_id=next_user_id)
            if not entry or entry.status != 'WAITING':
                continue

            offer_token, expires_at = generate_offer_token(next_user_id, session_id, expires_minutes)
            crud.session_waitlist.set_offer(db, entry=entry, offer_token=offer_token, expires_at=expires_at)
            crud.waitlist_event.log_event(
                db,
                waitlist_entry_id=entry.id,
                event_type='OFFERED',
                metadata={'offered_by': user.get("sub"), 'bulk_offer': True}
            )
            offers_sent += 1

        if offers_sent == 0:
            raise HTTPException(status_code=404, detail="No users in waitlist with WAITING status")

        logger.info(f"Admin {user.get('sub')} bulk sent {offers_sent} offers for session {session_id}")

        return BulkSendOffersResponseType(
            success=True,
            offers_sent=offers_sent,
            message=f"Successfully sent {offers_sent} offers"
        )

    @strawberry.mutation
    def update_session_capacity(
        self,
        input: UpdateCapacityInput,
        info: Info
    ) -> UpdateCapacityResponseType:
        """
        [ADMIN] Update session maximum capacity.

        Automatically sends offers if capacity increases.
        Requires admin or organizer authorization.
        """
        user = info.context.user
        if not user:
            raise HTTPException(status_code=401, detail="Authentication required")

        db = info.context.db
        redis_client = _get_redis_client(info)
        session_id = input.session_id
        new_capacity = input.capacity

        validate_session_id(session_id)

        # Check authorization
        _check_organizer_permission(db, user, session_id)

        # Get capacity
        capacity_obj = session_capacity_crud.get_or_create(db, session_id, default_capacity=100)
        old_capacity = capacity_obj.maximum_capacity
        current_attendance = capacity_obj.current_attendance

        if new_capacity < current_attendance:
            raise HTTPException(
                status_code=400,
                detail=f"Cannot set capacity ({new_capacity}) below current attendance ({current_attendance})"
            )

        # Update capacity
        updated_capacity = session_capacity_crud.update_maximum_capacity(db, session_id, new_capacity)
        if not updated_capacity:
            raise HTTPException(status_code=500, detail="Failed to update capacity")

        available_spots = new_capacity - current_attendance

        # Auto-send offers if capacity increased
        offers_auto_sent = 0
        if new_capacity > old_capacity and available_spots > 0:
            for _ in range(available_spots):
                next_user_id, next_priority = get_next_in_queue(session_id, redis_client)
                if not next_user_id:
                    break

                entry = crud.session_waitlist.get_active_entry(db, session_id=session_id, user_id=next_user_id)
                if not entry or entry.status != 'WAITING':
                    continue

                offer_token, expires_at = generate_offer_token(next_user_id, session_id, 5)
                crud.session_waitlist.set_offer(db, entry=entry, offer_token=offer_token, expires_at=expires_at)
                crud.waitlist_event.log_event(
                    db,
                    waitlist_entry_id=entry.id,
                    event_type='OFFERED',
                    metadata={
                        'offered_by': user.get("sub"),
                        'auto_offer_on_capacity_increase': True,
                        'old_capacity': old_capacity,
                        'new_capacity': new_capacity
                    }
                )
                offers_auto_sent += 1

        logger.info(
            f"Admin {user.get('sub')} updated capacity for session {session_id}: "
            f"{old_capacity} → {new_capacity}. Auto-sent {offers_auto_sent} offers."
        )

        return UpdateCapacityResponseType(
            session_id=session_id,
            maximum_capacity=updated_capacity.maximum_capacity,
            current_attendance=updated_capacity.current_attendance,
            available_spots=available_spots,
            is_available=available_spots > 0,
            offers_automatically_sent=offers_auto_sent
        )
