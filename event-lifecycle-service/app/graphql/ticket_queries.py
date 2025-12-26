# app/graphql/ticket_queries.py
"""
GraphQL queries for Ticket Management System
"""
import strawberry
from typing import Optional, List
from strawberry.types import Info

from app.graphql.ticket_types import (
    TicketTypeFullType,
    TicketType as TicketGQLType,
    PromoCodeFullType,
    PromoCodeValidationType,
    TicketConnection,
    EventTicketSummaryType,
    TicketTypeStatsType,
    CheckInStatsType,
    CartItemInput,
    TicketStatusEnum,
)
from app.graphql.payment_types import MoneyType, TicketTypeType
from app.services.ticket_management import ticket_management_service
from app.schemas.ticket_management import CartItem, Money


@strawberry.type
class TicketManagementQueries:
    """Queries for ticket management."""

    # ============================================
    # Ticket Types (Public - for purchase)
    # ============================================

    @strawberry.field
    async def eventTicketTypes(
        self,
        info: Info,
        eventId: str
    ) -> List[TicketTypeType]:
        """Get available ticket types for an event (attendee view)."""
        db = info.context.db
        ticket_types = ticket_management_service.get_available_ticket_types(
            db, eventId
        )
        return ticket_types

    # ============================================
    # Ticket Types (Organizer)
    # ============================================

    @strawberry.field
    async def eventTicketTypesAdmin(
        self,
        info: Info,
        eventId: str
    ) -> List[TicketTypeFullType]:
        """Get all ticket types including inactive (organizer view)."""
        db = info.context.db
        ticket_types = ticket_management_service.get_ticket_types_for_event(
            db, eventId, include_inactive=True, include_hidden=True
        )
        return ticket_types

    @strawberry.field
    async def ticketType(
        self,
        info: Info,
        id: str
    ) -> Optional[TicketTypeFullType]:
        """Get a single ticket type by ID."""
        db = info.context.db
        from app.crud.ticket_type_v2 import ticket_type_crud
        ticket_type = ticket_type_crud.get(db, id)
        return ticket_type

    @strawberry.field
    async def eventTicketSummary(
        self,
        info: Info,
        eventId: str
    ) -> EventTicketSummaryType:
        """Get comprehensive ticket summary for an event."""
        db = info.context.db
        summary = ticket_management_service.get_event_ticket_summary(db, eventId)

        return EventTicketSummaryType(
            eventId=summary.event_id,
            totalTicketTypes=summary.total_ticket_types,
            totalCapacity=summary.total_capacity,
            totalSold=summary.total_sold,
            totalRevenue=MoneyType(
                amount=summary.total_revenue.amount,
                currency=summary.total_revenue.currency
            ),
            ticketTypeStats=[
                TicketTypeStatsType(
                    ticketTypeId=stat.ticket_type_id,
                    ticketTypeName=stat.ticket_type_name,
                    quantitySold=stat.quantity_sold,
                    quantityAvailable=stat.quantity_available,
                    revenue=MoneyType(
                        amount=stat.revenue.amount,
                        currency=stat.revenue.currency
                    ),
                    percentageSold=stat.percentage_sold
                )
                for stat in summary.ticket_type_stats
            ],
            salesToday=summary.sales_today,
            salesThisWeek=summary.sales_this_week,
            salesThisMonth=summary.sales_this_month,
            revenueToday=MoneyType(
                amount=summary.revenue_today.amount,
                currency=summary.revenue_today.currency
            ),
            revenueThisWeek=MoneyType(
                amount=summary.revenue_this_week.amount,
                currency=summary.revenue_this_week.currency
            ),
            revenueThisMonth=MoneyType(
                amount=summary.revenue_this_month.amount,
                currency=summary.revenue_this_month.currency
            ),
        )

    # ============================================
    # Promo Codes (Organizer)
    # ============================================

    @strawberry.field
    async def eventPromoCodes(
        self,
        info: Info,
        eventId: str
    ) -> List[PromoCodeFullType]:
        """Get all promo codes for an event."""
        db = info.context.db
        promo_codes = ticket_management_service.get_promo_codes_for_event(
            db, eventId, include_inactive=True
        )
        return promo_codes

    @strawberry.field
    async def organizationPromoCodes(
        self,
        info: Info,
        organizationId: str
    ) -> List[PromoCodeFullType]:
        """Get organization-wide promo codes."""
        db = info.context.db
        promo_codes = ticket_management_service.get_organization_promo_codes(
            db, organizationId, org_wide_only=True
        )
        return promo_codes

    @strawberry.field
    async def promoCode(
        self,
        info: Info,
        id: str
    ) -> Optional[PromoCodeFullType]:
        """Get a single promo code by ID."""
        db = info.context.db
        from app.crud.promo_code_crud import promo_code_crud
        promo_code = promo_code_crud.get(db, id)
        return promo_code

    @strawberry.field
    async def validatePromoCode(
        self,
        info: Info,
        eventId: str,
        code: str,
        organizationId: str,
        cartItems: List[CartItemInput]
    ) -> PromoCodeValidationType:
        """Validate a promo code for a cart (public)."""
        db = info.context.db

        # Get user info from context if available (user is a dict from JWT)
        user = info.context.user
        user_id = user.get("sub") if user else None

        # Convert input to schema
        cart_items = [
            CartItem(
                ticket_type_id=item.ticketTypeId,
                quantity=item.quantity,
                price=item.price
            )
            for item in cartItems
        ]

        validation = ticket_management_service.validate_promo_code(
            db=db,
            code=code,
            event_id=eventId,
            organization_id=organizationId,
            cart_items=cart_items,
            user_id=user_id
        )

        # Convert to GraphQL type
        discount_amount = None
        if validation.discount_amount:
            discount_amount = MoneyType(
                amount=validation.discount_amount.amount,
                currency=validation.discount_amount.currency
            )

        promo_code = None
        if validation.promo_code:
            # Need to fetch the actual model for GraphQL type
            from app.crud.promo_code_crud import promo_code_crud
            promo_code = await promo_code_crud.get(db, validation.promo_code.id)

        return PromoCodeValidationType(
            isValid=validation.is_valid,
            promoCode=promo_code,
            discountAmount=discount_amount,
            errorCode=validation.error_code,
            errorMessage=validation.error_message
        )

    # ============================================
    # Tickets (Organizer)
    # ============================================

    @strawberry.field
    async def eventTickets(
        self,
        info: Info,
        eventId: str,
        status: Optional[TicketStatusEnum] = None,
        search: Optional[str] = None,
        first: int = 50,
        after: Optional[str] = None
    ) -> TicketConnection:
        """Get all tickets for an event (paginated)."""
        db = info.context.db

        # Parse cursor for offset
        offset = 0
        if after:
            try:
                offset = int(after)
            except ValueError:
                offset = 0

        status_str = status.value if status else None
        tickets, total = ticket_management_service.get_event_tickets(
            db=db,
            event_id=eventId,
            status=status_str,
            search=search,
            limit=first,
            offset=offset
        )

        has_next = offset + len(tickets) < total

        return TicketConnection(
            tickets=tickets,
            totalCount=total,
            hasNextPage=has_next
        )

    @strawberry.field
    async def ticketByCode(
        self,
        info: Info,
        eventId: str,
        ticketCode: str
    ) -> Optional[TicketGQLType]:
        """Get a ticket by its code (for check-in)."""
        db = info.context.db
        from app.crud.ticket_crud import ticket_crud
        ticket = ticket_crud.get_by_code(db, ticketCode, eventId)
        return ticket

    @strawberry.field
    async def ticket(
        self,
        info: Info,
        id: str
    ) -> Optional[TicketGQLType]:
        """Get a single ticket by ID."""
        db = info.context.db
        from app.crud.ticket_crud import ticket_crud
        ticket = ticket_crud.get(db, id)
        return ticket

    # ============================================
    # Tickets (Attendee)
    # ============================================

    @strawberry.field
    async def myTickets(
        self,
        info: Info,
        eventId: Optional[str] = None
    ) -> List[TicketGQLType]:
        """Get current user's tickets."""
        db = info.context.db
        user = info.context.user

        if not user:
            return []

        user_id = user.get("sub") if isinstance(user, dict) else user.id
        tickets = ticket_management_service.get_user_tickets(
            db, user_id, eventId
        )
        return tickets

    # ============================================
    # Check-in Stats
    # ============================================

    @strawberry.field
    async def checkInStats(
        self,
        info: Info,
        eventId: str
    ) -> CheckInStatsType:
        """Get check-in statistics for an event."""
        db = info.context.db
        from app.crud.ticket_crud import ticket_crud
        stats = ticket_crud.get_check_in_stats(db, eventId)

        return CheckInStatsType(
            total=stats["total"],
            checkedIn=stats["checked_in"],
            remaining=stats["remaining"],
            percentage=stats["percentage"]
        )
