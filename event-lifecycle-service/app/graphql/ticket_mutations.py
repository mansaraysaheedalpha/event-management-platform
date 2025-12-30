# app/graphql/ticket_mutations.py
"""
GraphQL mutations for Ticket Management System
"""
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
    async def checkInTicket(
        self,
        info: Info,
        input: CheckInTicketInput
    ) -> TicketGQLType:
        """Check in a ticket by code."""
        db = info.context.db
        user = info.context.user
        staff_user_id = user.get("sub") if user else "unknown"

        try:
            ticket = ticket_management_service.check_in_ticket(
                db=db,
                ticket_code=input.ticketCode,
                event_id=input.eventId,
                staff_user_id=staff_user_id,
                location=input.location
            )
            return ticket
        except ValueError as e:
            raise Exception(str(e))

    @strawberry.mutation
    async def reverseCheckIn(
        self,
        info: Info,
        ticketId: str
    ) -> TicketGQLType:
        """Reverse a check-in (undo)."""
        db = info.context.db

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

        try:
            ticket = ticket_management_service.cancel_ticket(
                db, input.ticketId, input.reason
            )
            return ticket
        except ValueError as e:
            raise Exception(str(e))

    @strawberry.mutation
    async def resendTicketEmail(
        self,
        info: Info,
        ticketId: str
    ) -> bool:
        """Resend ticket confirmation email."""
        db = info.context.db
        from app.crud.ticket_crud import ticket_crud

        ticket = ticket_crud.get(db, ticketId)
        if not ticket:
            raise Exception("Ticket not found")

        # Email sending will be handled by notification service integration
        # For now, return True to indicate the request was accepted
        # The actual email will be sent when notification service is integrated
        return True

    @strawberry.mutation
    async def transferTicket(
        self,
        info: Info,
        input: TransferTicketInput
    ) -> TicketGQLType:
        """Transfer a ticket to a new attendee."""
        db = info.context.db

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