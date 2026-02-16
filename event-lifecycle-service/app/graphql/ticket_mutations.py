# app/graphql/ticket_mutations.py
"""
GraphQL mutations for Ticket Management System
"""
import json
import logging
import strawberry
from typing import Optional, List
from strawberry.types import Info

from app.graphql.ticket_types import (
    TicketTypeFullType,
    TicketType as TicketGQLType,
    PromoCodeFullType,
    CreateTicketTypeInput,
    UpdateTicketTypeInput,
    ReorderTicketTypesInput,
    CreatePromoCodeInput,
    UpdatePromoCodeInput,
    CheckInTicketInput,
    TransferTicketInput,
    TransferMyTicketInput,
    CancelTicketInput,
    DiscountTypeEnum,
)
from app.services.ticket_management import ticket_management_service
from app.schemas.ticket_management import (
    TicketTypeCreate,
    TicketTypeUpdate,
    PromoCodeCreate,
    PromoCodeUpdate,
    DiscountType,
)
from app.utils.graphql_rate_limit import rate_limit

logger = logging.getLogger(__name__)


def _require_auth(info: Info) -> dict:
    """
    Require valid authentication. Returns the user dict.
    Raises Exception if no user or no sub claim.
    """
    user = info.context.user
    if not user or not user.get("sub"):
        raise Exception("Authentication required to check in tickets")
    return user


def _authorize_ticket_action(info: Info, event_id: str) -> str:
    """
    Authorize a ticket action (check-in, reverse, cancel) by verifying
    the user's org matches the event's org, or the user has
    'event:validate_tickets' permission.

    Returns the staff_user_id (user sub).
    Raises Exception if unauthorized.
    """
    user = _require_auth(info)
    staff_user_id = user["sub"]
    db = info.context.db

    # Query event to get its organization_id
    from app.models.event import Event
    event = db.query(Event).filter(Event.id == event_id).first()
    if not event:
        raise Exception("Event not found")

    # Check: user's orgId matches event's organization_id
    user_org_id = user.get("orgId")
    user_permissions = user.get("permissions", [])

    if user_org_id and user_org_id == event.organization_id:
        return staff_user_id

    # Check: user has 'event:validate_tickets' permission
    if "event:validate_tickets" in user_permissions:
        return staff_user_id

    raise Exception("You don't have permission to check in tickets for this event")


def _authorize_ticket_action_by_ticket_id(info: Info, ticket_id: str) -> str:
    """
    Authorize a ticket action when we only have a ticket_id (not event_id).
    Looks up the ticket to find the event_id, then delegates to
    _authorize_ticket_action.

    Returns the staff_user_id (user sub).
    Raises Exception if unauthorized or ticket not found.
    """
    db = info.context.db
    from app.crud.ticket_crud import ticket_crud

    ticket = ticket_crud.get(db, ticket_id)
    if not ticket:
        raise Exception("Ticket not found")

    return _authorize_ticket_action(info, ticket.event_id)


def _check_idempotency(idempotency_key: Optional[str], user_id: str) -> Optional[dict]:
    """
    Check if an idempotency key has already been used.
    Returns cached result dict if key exists, None otherwise.
    """
    if not idempotency_key:
        return None

    try:
        from app.db.redis import redis_client
        cache_key = f"idempotency:checkin:{user_id}:{idempotency_key}"
        cached = redis_client.get(cache_key)
        if cached:
            return json.loads(cached)
    except Exception as e:
        logger.warning(f"Redis idempotency check failed: {e}")

    return None


def _store_idempotency(idempotency_key: Optional[str], user_id: str, ticket_id: str) -> None:
    """
    Store an idempotency key with the result ticket ID.
    Uses SET NX with 60-second TTL.
    """
    if not idempotency_key:
        return

    try:
        from app.db.redis import redis_client
        cache_key = f"idempotency:checkin:{user_id}:{idempotency_key}"
        result_data = json.dumps({"ticket_id": ticket_id})
        redis_client.set(cache_key, result_data, ex=60, nx=True)
    except Exception as e:
        logger.warning(f"Redis idempotency store failed: {e}")


@strawberry.type
class TicketManagementMutations:
    """Mutations for ticket management."""

    # ============================================
    # Ticket Type Management (Organizer)
    # ============================================

    @strawberry.mutation
    async def createTicketType(
        self,
        info: Info,
        input: CreateTicketTypeInput,
        organizationId: str
    ) -> TicketTypeFullType:
        """Create a new ticket type."""
        db = info.context.db
        user = info.context.user
        user_id = user.get("sub") if user else None

        # Convert GraphQL input to Pydantic schema
        create_data = TicketTypeCreate(
            event_id=input.eventId,
            name=input.name,
            description=input.description,
            price=input.price,
            currency=input.currency,
            quantity_total=input.quantityTotal,
            min_per_order=input.minPerOrder,
            max_per_order=input.maxPerOrder,
            sales_start_at=input.salesStartAt,
            sales_end_at=input.salesEndAt,
            is_hidden=input.isHidden,
            sort_order=input.sortOrder,
        )

        ticket_type = ticket_management_service.create_ticket_type(
            db, create_data, organizationId, user_id
        )
        return ticket_type

    @strawberry.mutation
    async def updateTicketType(
        self,
        info: Info,
        id: str,
        input: UpdateTicketTypeInput
    ) -> Optional[TicketTypeFullType]:
        """Update a ticket type."""
        db = info.context.db

        # Convert GraphQL input to Pydantic schema
        update_data = TicketTypeUpdate(
            name=input.name,
            description=input.description,
            price=input.price,
            currency=input.currency,
            quantity_total=input.quantityTotal,
            min_per_order=input.minPerOrder,
            max_per_order=input.maxPerOrder,
            sales_start_at=input.salesStartAt,
            sales_end_at=input.salesEndAt,
            is_active=input.isActive,
            is_hidden=input.isHidden,
            sort_order=input.sortOrder,
        )

        ticket_type = ticket_management_service.update_ticket_type(
            db, id, update_data
        )
        return ticket_type

    @strawberry.mutation
    async def deleteTicketType(
        self,
        info: Info,
        id: str
    ) -> bool:
        """Delete a ticket type (only if no sales)."""
        db = info.context.db
        try:
            return ticket_management_service.delete_ticket_type(db, id)
        except ValueError as e:
            raise Exception(str(e))

    @strawberry.mutation
    async def reorderTicketTypes(
        self,
        info: Info,
        input: ReorderTicketTypesInput
    ) -> List[TicketTypeFullType]:
        """Reorder ticket types for an event."""
        db = info.context.db
        ticket_types = ticket_management_service.reorder_ticket_types(
            db, input.eventId, input.ticketTypeIds
        )
        return ticket_types

    @strawberry.mutation
    async def duplicateTicketType(
        self,
        info: Info,
        id: str
    ) -> Optional[TicketTypeFullType]:
        """Duplicate a ticket type."""
        db = info.context.db
        user = info.context.user
        user_id = user.get("sub") if user else None

        ticket_type = ticket_management_service.duplicate_ticket_type(
            db, id, user_id
        )
        return ticket_type

    # ============================================
    # Promo Code Management (Organizer)
    # ============================================

    @strawberry.mutation
    async def createPromoCode(
        self,
        info: Info,
        input: CreatePromoCodeInput,
        organizationId: str
    ) -> PromoCodeFullType:
        """Create a new promo code."""
        db = info.context.db
        user = info.context.user
        user_id = user.get("sub") if user else None

        # Convert GraphQL enum to Pydantic enum
        discount_type = DiscountType(input.discountType.value)

        # Convert GraphQL input to Pydantic schema
        create_data = PromoCodeCreate(
            event_id=input.eventId,
            code=input.code,
            description=input.description,
            discount_type=discount_type,
            discount_value=input.discountValue,
            applicable_ticket_type_ids=input.applicableTicketTypeIds,
            max_uses=input.maxUses,
            max_uses_per_user=input.maxUsesPerUser,
            valid_from=input.validFrom,
            valid_until=input.validUntil,
            minimum_order_amount=input.minimumOrderAmount,
            minimum_tickets=input.minimumTickets,
        )

        promo_code = ticket_management_service.create_promo_code(
            db, create_data, organizationId, user_id
        )
        return promo_code

    @strawberry.mutation
    def updatePromoCode(
        self,
        info: Info,
        id: str,
        input: UpdatePromoCodeInput
    ) -> Optional[PromoCodeFullType]:
        """Update a promo code."""
        db = info.context.db

        # Build update dict with only provided (non-None) values
        # This ensures exclude_unset=True works correctly in CRUD
        update_dict = {}

        if input.description is not None:
            update_dict["description"] = input.description

        if input.discountType:
            update_dict["discount_type"] = DiscountType(input.discountType.value)

        if input.discountValue is not None:
            update_dict["discount_value"] = input.discountValue

        if input.applicableTicketTypeIds is not None:
            update_dict["applicable_ticket_type_ids"] = input.applicableTicketTypeIds

        if input.maxUses is not None:
            update_dict["max_uses"] = input.maxUses

        if input.maxUsesPerUser is not None:
            update_dict["max_uses_per_user"] = input.maxUsesPerUser

        if input.validFrom is not None:
            update_dict["valid_from"] = input.validFrom

        if input.validUntil is not None:
            update_dict["valid_until"] = input.validUntil

        if input.minimumOrderAmount is not None:
            update_dict["minimum_order_amount"] = input.minimumOrderAmount

        if input.minimumTickets is not None:
            update_dict["minimum_tickets"] = input.minimumTickets

        if input.isActive is not None:
            update_dict["is_active"] = input.isActive

        # Convert to Pydantic schema using unpacked dict
        # Fields missing from update_dict will use default values and count as unset
        update_data = PromoCodeUpdate(**update_dict)

        promo_code = ticket_management_service.update_promo_code(
            db, id, update_data
        )
        return promo_code

    @strawberry.mutation
    async def deletePromoCode(
        self,
        info: Info,
        id: str
    ) -> bool:
        """Delete a promo code."""
        db = info.context.db
        return ticket_management_service.delete_promo_code(db, id)

    @strawberry.mutation
    async def deactivatePromoCode(
        self,
        info: Info,
        id: str
    ) -> Optional[PromoCodeFullType]:
        """Deactivate a promo code (soft disable)."""
        db = info.context.db
        return ticket_management_service.deactivate_promo_code(db, id)

    # ============================================
    # Ticket Check-in (Organizer/Staff)
    # ============================================

    @strawberry.mutation
    @rate_limit(max_calls=60, period_seconds=60)  # 60 check-ins per minute per user
    async def checkInTicket(
        self,
        info: Info,
        input: CheckInTicketInput
    ) -> TicketGQLType:
        """Check in a ticket by code."""
        db = info.context.db

        # BUG H3 fix: Require valid authentication (no "unknown" fallback)
        # BUG C3 fix: Authorize user for this event
        staff_user_id = _authorize_ticket_action(info, input.eventId)

        # BUG M1 fix: Check idempotency key
        if input.idempotencyKey:
            cached = _check_idempotency(input.idempotencyKey, staff_user_id)
            if cached:
                # Return the previously checked-in ticket
                from app.crud.ticket_crud import ticket_crud
                existing_ticket = ticket_crud.get(db, cached["ticket_id"])
                if existing_ticket:
                    return existing_ticket

        try:
            ticket = ticket_management_service.check_in_ticket(
                db=db,
                ticket_code=input.ticketCode,
                event_id=input.eventId,
                staff_user_id=staff_user_id,
                location=input.location
            )

            # BUG M1 fix: Store idempotency key on success
            _store_idempotency(input.idempotencyKey, staff_user_id, ticket.id)

            return ticket
        except ValueError as e:
            raise Exception(str(e))

    @strawberry.mutation
    @rate_limit(max_calls=10, period_seconds=60)  # 10 reversals per minute per user
    async def reverseCheckIn(
        self,
        info: Info,
        ticketId: str
    ) -> TicketGQLType:
        """Reverse a check-in (undo)."""
        db = info.context.db

        # BUG H3 fix: Require valid authentication
        # BUG C3 fix: Authorize user for this event (lookup event via ticket)
        _authorize_ticket_action_by_ticket_id(info, ticketId)

        try:
            ticket = ticket_management_service.reverse_check_in(db, ticketId)
            return ticket
        except ValueError as e:
            raise Exception(str(e))

    # ============================================
    # Ticket Management (Organizer)
    # ============================================

    @strawberry.mutation
    async def cancelTicket(
        self,
        info: Info,
        input: CancelTicketInput
    ) -> TicketGQLType:
        """Cancel a ticket."""
        db = info.context.db

        # BUG C3 fix: Authorize user for this event (lookup event via ticket)
        _authorize_ticket_action_by_ticket_id(info, input.ticketId)

        try:
            ticket = ticket_management_service.cancel_ticket(
                db, input.ticketId, input.reason
            )
            return ticket
        except ValueError as e:
            raise Exception(str(e))

    @strawberry.mutation
    @rate_limit(max_calls=3, period_seconds=3600)
    async def resendTicketEmail(
        self,
        info: Info,
        ticketId: str
    ) -> bool:
        """Resend ticket confirmation email.

        Rate-limited to 3 resends per ticket per hour.
        Requires authentication: ticket owner or org admin.
        """
        user = _require_auth(info)
        db = info.context.db
        from app.crud.ticket_crud import ticket_crud

        ticket = ticket_crud.get(db, ticketId)
        if not ticket:
            raise Exception("Ticket not found")

        # Authorize: ticket owner OR org admin
        is_owner = ticket.user_id and ticket.user_id == user.get("sub")
        is_org_admin = False
        if ticket.event:
            is_org_admin = (
                user.get("orgId")
                and user.get("orgId") == ticket.event.organization_id
            )
        if not is_owner and not is_org_admin:
            raise Exception("Not authorized to resend this ticket email")

        # Send the email via existing Resend infrastructure
        from app.core.email import send_registration_confirmation

        event = ticket.event
        event_date = ""
        if event and event.start_date:
            event_date = event.start_date.strftime("%B %d, %Y at %I:%M %p")

        event_location = None
        if event and hasattr(event, "venue") and event.venue:
            event_location = event.venue.name

        result = send_registration_confirmation(
            to_email=ticket.attendee_email,
            recipient_name=ticket.attendee_name,
            event_name=event.name if event else "Your Event",
            event_date=event_date,
            ticket_code=ticket.ticket_code,
            event_location=event_location,
        )

        if result and result.get("success") is False:
            logger.warning(
                f"Failed to resend ticket email for {ticket.ticket_code}: "
                f"{result.get('error', 'unknown')}"
            )
            raise Exception("Failed to send email. Please try again later.")

        logger.info(f"Resent ticket email for {ticket.ticket_code}")
        return True

    @strawberry.mutation
    async def transferTicket(
        self,
        info: Info,
        input: TransferTicketInput
    ) -> TicketGQLType:
        """Transfer a ticket to a new attendee (org admin action)."""
        db = info.context.db

        # BUG C3 fix: Authorize user for this event (lookup event via ticket)
        _authorize_ticket_action_by_ticket_id(info, input.ticketId)

        try:
            ticket = ticket_management_service.transfer_ticket(
                db=db,
                ticket_id=input.ticketId,
                new_attendee_name=input.newAttendeeName,
                new_attendee_email=input.newAttendeeEmail
            )
            return ticket
        except ValueError as e:
            raise Exception(str(e))

    @strawberry.mutation
    async def transferMyTicket(
        self,
        info: Info,
        input: TransferMyTicketInput
    ) -> bool:
        """Transfer an attendee's own ticket to a new person.

        Attendee-facing: looks up by ticket code, verifies the caller
        is the ticket owner (user_id match). Works with both Ticket
        and Registration models.
        """
        user = _require_auth(info)
        caller_id = user["sub"]
        db = info.context.db

        from app.crud.ticket_crud import ticket_crud
        from app.models.registration import Registration

        # Try Ticket model first (paid events)
        ticket = ticket_crud.get_by_code(db, input.ticketCode)
        if ticket:
            if ticket.user_id != caller_id:
                raise Exception("You can only transfer your own tickets")
            if ticket.status != "valid":
                raise Exception(
                    f"Ticket cannot be transferred (current status: {ticket.status})"
                )
            try:
                ticket_crud.transfer(
                    db,
                    ticket.id,
                    new_attendee_name=input.newAttendeeName,
                    new_attendee_email=input.newAttendeeEmail,
                )
                logger.info(
                    f"Attendee transfer: {ticket.ticket_code} -> {input.newAttendeeEmail}"
                )
                return True
            except ValueError as e:
                raise Exception(str(e))

        # Fall back to Registration model (free events)
        reg = (
            db.query(Registration)
            .filter(Registration.ticket_code == input.ticketCode)
            .first()
        )
        if not reg:
            raise Exception("Ticket not found")

        if reg.user_id != caller_id:
            raise Exception("You can only transfer your own tickets")

        if reg.status != "confirmed":
            raise Exception(
                f"Ticket cannot be transferred (current status: {reg.status})"
            )

        # Transfer registration: update to new attendee
        from datetime import datetime, timezone
        reg.guest_name = input.newAttendeeName
        reg.guest_email = input.newAttendeeEmail
        reg.user_id = None  # Disassociate from current user
        db.commit()

        logger.info(
            f"Registration transfer: {reg.ticket_code} -> {input.newAttendeeEmail}"
        )
        return True
