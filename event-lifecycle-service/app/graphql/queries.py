# app/graphql/queries.py
import strawberry
import typing
from typing import List, Optional
from strawberry.types import Info
from fastapi import HTTPException
import httpx
from ..core.config import settings
from .. import crud
from .types import (
    EventType,
    SpeakerType,
    SessionType,
    RegistrationType,
    EventsPayload,
    EventStatsType,
    VenueType,
    BlueprintType,
    DomainEventType,
    MyRegistrationType,
    PublicEventsResponse,
    # Dashboard types
    OrganizationDashboardStatsType,
    WeeklyAttendanceResponse,
    WeeklyAttendanceDataPoint,
    EngagementTrendResponse,
    EngagementTrendDataPoint,
    EngagementBreakdownType,
    # Monetization types
    AdType,
    OfferType,
)
from .payment_types import (
    TicketTypeType,
    OrderType,
    OrderConnection,
    PaymentType,
    RefundType,
    OrderStatusEnum,
)
from .ticket_types import (
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
from . import payment_queries
from . import ticket_queries
from .waitlist_types import (
    WaitlistEntryType,
    WaitlistPositionType,
    SessionCapacityType,
    WaitlistStatsType,
    EventWaitlistAnalyticsType,
)
from .waitlist_queries import WaitlistQuery


@strawberry.type
class Query:
    @strawberry.field
    def event(self, id: strawberry.ID, info: Info) -> Optional[EventType]:
        db = info.context.db
        user = info.context.user
        event_id = str(id)
        event_obj = crud.event.get(db, id=event_id)
        if not event_obj:
            return None

        # --- AUTHORIZATION LOGIC ---
        # Determine if user can access this event
        can_access = False

        # Case 1: Event is public and not archived - anyone can view (authenticated or not)
        if event_obj.is_public and not event_obj.is_archived:
            can_access = True
        elif user:
            user_org_id = user.get("orgId")
            user_id = user.get("sub")

            # Case 2: User is an organizer in the same organization
            if user_org_id and event_obj.organization_id == user_org_id:
                can_access = True
            # Case 3: User is registered for this event (attendees can view non-public events)
            elif user_id:
                from ..models.registration import Registration
                registration = (
                    db.query(Registration)
                    .filter(
                        Registration.event_id == event_id,
                        Registration.user_id == user_id,
                        Registration.is_archived == "false",
                        Registration.status != "cancelled",
                    )
                    .first()
                )
                if registration:
                    can_access = True

        if not can_access:
            return None
        # ------------------------

        from ..crud import crud_registration

        registrations_count = crud_registration.registration.get_count_by_event(
            db, event_id=event_obj.id
        )
        event_dict = {
            c.name: getattr(event_obj, c.name) for c in event_obj.__table__.columns
        }
        event_dict["registrationsCount"] = registrations_count
        return event_dict

    # --- ADD THIS NEW PUBLIC QUERY ---
    @strawberry.field
    def publicSessionsByEvent(
        self, eventId: strawberry.ID, info: Info
    ) -> List[SessionType]:
        """
        Publicly fetches sessions for a single event, but only if the event
        is published and not archived.
        """
        db = info.context.db
        event = crud.event.get(db, id=str(eventId))

        if not event or not event.is_public or event.is_archived:
            raise HTTPException(
                status_code=404, detail="Event not found or is not public"
            )

        return crud.session.get_multi_by_event(db, event_id=str(eventId))

    # -------------------------------
    @strawberry.field
    def eventsByOrganization(
        self,
        info: Info,
        search: typing.Optional[str] = None,
        status: typing.Optional[str] = None,
        sortBy: typing.Optional[str] = "start_date",
        sortDirection: typing.Optional[str] = "desc",
        limit: typing.Optional[int] = 100,
        offset: typing.Optional[int] = 0,
    ) -> EventsPayload:
        if not info.context.user or not info.context.user.get("orgId"):
            raise HTTPException(
                status_code=403, detail="Not authorized or orgId missing from context"
            )
        db = info.context.db
        org_id = info.context.user["orgId"]
        payload_data = crud.event.get_multi_by_organization(
            db,
            org_id=org_id,
            search=search,
            status=status,
            sort_by=sortBy,
            sort_direction=sortDirection,
            skip=offset,
            limit=limit,
        )
        return EventsPayload(
            events=payload_data["events"], totalCount=payload_data["totalCount"]
        )

    @strawberry.field
    def eventStats(self, info: Info) -> EventStatsType:
        if not info.context.user or not info.context.user.get("orgId"):
            raise HTTPException(
                status_code=403, detail="Not authorized or orgId missing from context"
            )
        db = info.context.db
        org_id = info.context.user["orgId"]
        stats_data = crud.event.get_event_stats(db, org_id=org_id)
        return EventStatsType(
            totalEvents=stats_data["totalEvents"],
            upcomingEvents=stats_data["upcomingEvents"],
            upcomingRegistrations=stats_data["upcomingRegistrations"],
        )

    @strawberry.field
    def organizationSpeakers(self, info: Info) -> List[SpeakerType]:
        if not info.context.user or not info.context.user.get("orgId"):
            raise HTTPException(status_code=403, detail="Not authorized")
        db = info.context.db
        org_id = info.context.user["orgId"]
        return crud.speaker.get_multi_by_organization(db, org_id=org_id)

    @strawberry.field
    def speaker(self, id: strawberry.ID, info: Info) -> Optional[SpeakerType]:
        user = info.context.user
        if not user or not user.get("orgId"):
            raise HTTPException(status_code=403, detail="Not authorized")
        db = info.context.db
        org_id = user["orgId"]
        speaker_obj = crud.speaker.get(db, id=str(id))
        if not speaker_obj or speaker_obj.organization_id != org_id:
            return None
        return speaker_obj

    @strawberry.field
    def sessionsByEvent(self, eventId: strawberry.ID, info: Info) -> List[SessionType]:
        user = info.context.user
        if not user or not user.get("orgId"):
            raise HTTPException(status_code=403, detail="Not authorized")
        db = info.context.db
        org_id = user["orgId"]

        # First, verify the user has access to this event
        event = crud.event.get(db, id=str(eventId))
        if not event or event.organization_id != org_id:
            raise HTTPException(status_code=404, detail="Event not found")

        return crud.session.get_multi_by_event(db, event_id=str(eventId))

    @strawberry.field
    def organizationVenues(self, info: Info) -> List[VenueType]:
        user = info.context.user
        if not user or not user.get("orgId"):
            raise HTTPException(status_code=403, detail="Not authorized")
        db = info.context.db
        org_id = user["orgId"]
        # Assuming get_multi_by_organization also filters out archived items
        return crud.venue.get_multi_by_organization(db, org_id=org_id)

    @strawberry.field
    def venue(self, id: strawberry.ID, info: Info) -> Optional[VenueType]:
        user = info.context.user
        if not user or not user.get("orgId"):
            raise HTTPException(status_code=403, detail="Not authorized")
        db = info.context.db
        org_id = user["orgId"]

        venue_obj = crud.venue.get(db, id=str(id))
        if not venue_obj or venue_obj.organization_id != org_id:
            return None

        return venue_obj

    @strawberry.field
    def registrationsByEvent(
        self, eventId: strawberry.ID, info: Info
    ) -> List[RegistrationType]:
        if not info.context.user or not info.context.user.get("orgId"):
            raise HTTPException(status_code=403, detail="Not authorized")
        db = info.context.db
        return crud.registration.get_multi_by_event(db, event_id=str(eventId))

    @strawberry.field
    def organizationBlueprints(self, info: Info) -> List[BlueprintType]:
        user = info.context.user
        if not user or not user.get("orgId"):
            raise HTTPException(status_code=403, detail="Not authorized")
        db = info.context.db
        org_id = user["orgId"]
        return crud.blueprint.get_multi_by_organization(db, org_id=org_id)

    @strawberry.field
    def eventHistory(self, eventId: strawberry.ID, info: Info) -> List[DomainEventType]:
        """
        Retrieves a chronological log of all domain events for a specific event.
        """
        user = info.context.user
        if not user or not user.get("orgId"):
            raise HTTPException(status_code=403, detail="Not authorized")

        db = info.context.db
        org_id = user["orgId"]

        # First, verify the user has access to this event
        event = crud.event.get(db, id=str(eventId))
        if not event or event.organization_id != org_id:
            raise HTTPException(status_code=404, detail="Event not found")

        return crud.domain_event.get_for_event(db, event_id=str(eventId))

    @strawberry.field
    def myRegistrations(self, info: Info) -> List[MyRegistrationType]:
        """
        Returns all registrations for the currently authenticated user.
        This is for attendees to view their own event registrations.
        """
        user = info.context.user
        if not user or not user.get("sub"):
            raise HTTPException(status_code=401, detail="Authentication required")

        db = info.context.db
        user_id = user["sub"]

        # Get all registrations for this user with their associated events
        registrations = crud.registration.get_multi_by_user(db, user_id=user_id)
        return registrations

    @strawberry.field
    def myRegistrationForEvent(
        self, eventId: strawberry.ID, info: Info
    ) -> Optional[MyRegistrationType]:
        """
        Returns the current user's registration for a specific event, if one exists.
        This is used to check if the user is already registered for an event.
        """
        user = info.context.user
        if not user or not user.get("sub"):
            raise HTTPException(status_code=401, detail="Authentication required")

        db = info.context.db
        user_id = user["sub"]

        # Get the registration for this user and event
        registration = crud.registration.get_by_user_or_email(
            db, event_id=str(eventId), user_id=user_id
        )
        return registration

    @strawberry.field
    def publicEvents(
        self,
        info: Info,
        search: typing.Optional[str] = None,
        limit: typing.Optional[int] = 100,
        offset: typing.Optional[int] = 0,
        includePast: typing.Optional[bool] = False,
    ) -> PublicEventsResponse:
        """
        Returns all published, public events for the event discovery page.
        No authentication required.
        """
        db = info.context.db
        payload_data = crud.event.get_public_events(
            db,
            search=search,
            skip=offset,
            limit=limit,
            include_past=includePast,
        )
        return PublicEventsResponse(
            events=payload_data["events"],
            totalCount=payload_data["totalCount"],
        )

    # --- ORGANIZER DASHBOARD QUERIES ---

    @strawberry.field
    def organizationDashboardStats(self, info: Info) -> OrganizationDashboardStatsType:
        """
        Returns dashboard statistics for the current organization.
        Includes total attendees, active sessions, engagement rate, and total events.
        Engagement rate is calculated from real-time service data (Q&A, polls, chat).
        """
        user = info.context.user
        if not user or not user.get("orgId"):
            raise HTTPException(
                status_code=403, detail="Not authorized or orgId missing from context"
            )

        db = info.context.db
        org_id = user["orgId"]

        stats = crud.dashboard.get_dashboard_stats(db, org_id=org_id)

        # Calculate avg engagement from real-time service data
        avg_engagement_rate = stats["avgEngagementRate"]  # Default to check-in rate
        try:
            total_attendees = stats["totalAttendees"]
            if total_attendees > 0:
                real_time_url = settings.REAL_TIME_SERVICE_URL_INTERNAL
                params = {"totalAttendees": str(total_attendees), "orgId": org_id}

                with httpx.Client(timeout=5.0) as client:
                    response = client.get(
                        f"{real_time_url}/internal/dashboard/engagement-breakdown",
                        params=params,
                        headers={"X-Internal-Api-Key": settings.INTERNAL_API_KEY},
                    )

                    if response.status_code == 200:
                        data = response.json()
                        # Average of Q&A, poll, and chat participation rates
                        qa_rate = data.get("qaParticipation", 0)
                        poll_rate = data.get("pollResponseRate", 0)
                        chat_rate = data.get("chatActivityRate", 0)
                        # Only average non-zero rates to avoid dilution
                        rates = [r for r in [qa_rate, poll_rate, chat_rate] if r > 0]
                        if rates:
                            avg_engagement_rate = round(sum(rates) / len(rates), 1)
        except Exception as e:
            import logging
            logging.warning(f"Failed to fetch engagement data for avg rate: {e}")

        return OrganizationDashboardStatsType(
            totalAttendees=stats["totalAttendees"],
            totalAttendeesChange=stats["totalAttendeesChange"],
            activeSessions=stats["activeSessions"],
            activeSessionsChange=stats["activeSessionsChange"],
            avgEngagementRate=avg_engagement_rate,
            avgEngagementChange=stats["avgEngagementChange"],
            totalEvents=stats["totalEvents"],
            totalEventsChange=stats["totalEventsChange"],
        )

    @strawberry.field
    def weeklyAttendance(
        self, info: Info, days: typing.Optional[int] = 7
    ) -> WeeklyAttendanceResponse:
        """
        Returns daily attendance data for the last N days.
        Used for the attendance chart on the dashboard.
        """
        user = info.context.user
        if not user or not user.get("orgId"):
            raise HTTPException(
                status_code=403, detail="Not authorized or orgId missing from context"
            )

        db = info.context.db
        org_id = user["orgId"]

        attendance_data = crud.dashboard.get_weekly_attendance(
            db, org_id=org_id, days=days
        )

        data_points = [
            WeeklyAttendanceDataPoint(
                label=item["label"],
                date=item["date"],
                value=item["value"],
            )
            for item in attendance_data
        ]

        return WeeklyAttendanceResponse(data=data_points)

    @strawberry.field
    def engagementTrend(
        self, info: Info, periods: typing.Optional[int] = 12
    ) -> EngagementTrendResponse:
        """
        Returns engagement trend data for sparkline visualization.
        Shows normalized engagement scores over the last N periods.
        """
        user = info.context.user
        if not user or not user.get("orgId"):
            raise HTTPException(
                status_code=403, detail="Not authorized or orgId missing from context"
            )

        db = info.context.db
        org_id = user["orgId"]

        trend_data = crud.dashboard.get_registration_trend(
            db, org_id=org_id, periods=periods
        )

        data_points = [
            EngagementTrendDataPoint(
                period=item["period"],
                value=item["value"],
            )
            for item in trend_data
        ]

        return EngagementTrendResponse(data=data_points)

    @strawberry.field
    def engagementBreakdown(
        self, info: Info, eventId: typing.Optional[strawberry.ID] = None
    ) -> EngagementBreakdownType:
        """
        Returns detailed engagement breakdown metrics.
        Shows Q&A, poll, and chat participation rates.
        If eventId is provided, scopes to that event; otherwise aggregates across all org events.

        Fetches data from the real-time service via internal API
        for accurate engagement metrics (Q&A questions, poll votes, chat messages).
        """
        user = info.context.user
        if not user or not user.get("orgId"):
            raise HTTPException(
                status_code=403, detail="Not authorized or orgId missing from context"
            )

        db = info.context.db
        org_id = user["orgId"]

        # Get total attendees for calculating rates
        if eventId:
            # Verify event belongs to org
            event = crud.event.get(db, id=str(eventId))
            if not event or event.organization_id != org_id:
                raise HTTPException(status_code=404, detail="Event not found")
            total_attendees = crud.registration.get_count_by_event(
                db, event_id=str(eventId)
            )
        else:
            total_attendees = crud.dashboard.get_total_registrations(db, org_id=org_id)

        # Fetch engagement data from real-time service
        try:
            real_time_url = settings.REAL_TIME_SERVICE_URL_INTERNAL
            params = {"totalAttendees": str(total_attendees)}
            if eventId:
                params["eventId"] = str(eventId)
            else:
                params["orgId"] = org_id

            with httpx.Client(timeout=10.0) as client:
                response = client.get(
                    f"{real_time_url}/internal/dashboard/engagement-breakdown",
                    params=params,
                    headers={"X-Internal-Api-Key": settings.INTERNAL_API_KEY},
                )

                if response.status_code == 200:
                    data = response.json()
                    return EngagementBreakdownType(
                        qaParticipation=data.get("qaParticipation", 0.0),
                        qaParticipationCount=data.get("qaParticipationCount", 0),
                        qaTotal=data.get("qaTotal", total_attendees),
                        pollResponseRate=data.get("pollResponseRate", 0.0),
                        pollResponseCount=data.get("pollResponseCount", 0),
                        pollTotal=data.get("pollTotal", total_attendees),
                        chatActivityRate=data.get("chatActivityRate", 0.0),
                        chatMessageCount=data.get("chatMessageCount", 0),
                        chatParticipants=data.get("chatParticipants", 0),
                        chatTotal=data.get("chatTotal", total_attendees),
                    )
        except Exception as e:
            # Log the error but return default values
            import logging
            logging.warning(f"Failed to fetch engagement breakdown from real-time service: {e}")

        # Return default values if real-time service is unavailable
        return EngagementBreakdownType(
            qaParticipation=0.0,
            qaParticipationCount=0,
            qaTotal=total_attendees,
            pollResponseRate=0.0,
            pollResponseCount=0,
            pollTotal=total_attendees,
            chatActivityRate=0.0,
            chatMessageCount=0,
            chatParticipants=0,
            chatTotal=total_attendees,
        )

    # --- PAYMENT QUERIES ---

    @strawberry.field
    def eventTicketTypes(
        self, eventId: strawberry.ID, info: Info
    ) -> List[TicketTypeType]:
        """
        Get available ticket types for an event (public).
        Returns only active, on-sale ticket types.
        """
        return payment_queries.get_event_ticket_types(str(eventId), info)

    @strawberry.field
    def order(self, orderId: strawberry.ID, info: Info) -> Optional[OrderType]:
        """
        Get order by ID (authenticated - owner or organizer only).
        """
        return payment_queries.get_order(str(orderId), info)

    @strawberry.field
    def orderByNumber(
        self, orderNumber: str, info: Info
    ) -> Optional[OrderType]:
        """
        Get order by order number (for confirmation pages).
        """
        return payment_queries.get_order_by_number(orderNumber, info)

    @strawberry.field
    def myOrders(
        self,
        info: Info,
        status: Optional[OrderStatusEnum] = None,
        first: int = 20,
        after: Optional[str] = None,
    ) -> OrderConnection:
        """
        List orders for current authenticated user.
        """
        return payment_queries.get_my_orders(info, status, first, after)

    @strawberry.field
    def eventOrders(
        self,
        eventId: strawberry.ID,
        info: Info,
        status: Optional[OrderStatusEnum] = None,
        search: Optional[str] = None,
        first: int = 50,
        after: Optional[str] = None,
    ) -> OrderConnection:
        """
        List orders for an event (organizer only).
        """
        return payment_queries.get_event_orders(
            str(eventId), info, status, search, first, after
        )

    @strawberry.field
    def payment(self, paymentId: strawberry.ID, info: Info) -> Optional[PaymentType]:
        """
        Get payment details (authenticated - owner or organizer only).
        """
        return payment_queries.get_payment(str(paymentId), info)

    @strawberry.field
    def orderRefunds(self, orderId: strawberry.ID, info: Info) -> List[RefundType]:
        """
        Get refunds for an order (organizer only).
        """
        return payment_queries.get_order_refunds(str(orderId), info)

    @strawberry.field
    def ticketTypesByEvent(
        self, eventId: strawberry.ID, info: Info
    ) -> List[TicketTypeType]:
        """
        Get all ticket types for an event including inactive (organizer only).
        """
        return payment_queries.get_ticket_types_by_event(str(eventId), info)

    # --- TICKET MANAGEMENT QUERIES ---

    @strawberry.field
    async def eventTicketTypesAdmin(
        self, eventId: strawberry.ID, info: Info
    ) -> List[TicketTypeFullType]:
        """
        Get all ticket types including inactive (organizer view).
        """
        tq = ticket_queries.TicketManagementQueries()
        return await tq.eventTicketTypesAdmin(info, str(eventId))

    @strawberry.field
    async def ticketType(
        self, id: strawberry.ID, info: Info
    ) -> Optional[TicketTypeFullType]:
        """Get a single ticket type by ID."""
        tq = ticket_queries.TicketManagementQueries()
        return await tq.ticketType(info, str(id))

    @strawberry.field
    async def eventTicketSummary(
        self, eventId: strawberry.ID, info: Info
    ) -> EventTicketSummaryType:
        """Get comprehensive ticket summary for an event."""
        tq = ticket_queries.TicketManagementQueries()
        return await tq.eventTicketSummary(info, str(eventId))

    @strawberry.field
    async def eventPromoCodes(
        self, eventId: strawberry.ID, info: Info
    ) -> List[PromoCodeFullType]:
        """Get all promo codes for an event."""
        tq = ticket_queries.TicketManagementQueries()
        return await tq.eventPromoCodes(info, str(eventId))

    @strawberry.field
    async def organizationPromoCodes(
        self, organizationId: str, info: Info
    ) -> List[PromoCodeFullType]:
        """Get organization-wide promo codes."""
        tq = ticket_queries.TicketManagementQueries()
        return await tq.organizationPromoCodes(info, organizationId)

    @strawberry.field
    async def promoCode(
        self, id: strawberry.ID, info: Info
    ) -> Optional[PromoCodeFullType]:
        """Get a single promo code by ID."""
        tq = ticket_queries.TicketManagementQueries()
        return await tq.promoCode(info, str(id))

    @strawberry.field
    async def validatePromoCode(
        self,
        eventId: strawberry.ID,
        code: str,
        organizationId: str,
        cartItems: List[CartItemInput],
        info: Info,
    ) -> PromoCodeValidationType:
        """Validate a promo code for a cart (public)."""
        tq = ticket_queries.TicketManagementQueries()
        return await tq.validatePromoCode(info, str(eventId), code, organizationId, cartItems)

    @strawberry.field
    async def eventTicketsAdmin(
        self,
        eventId: strawberry.ID,
        info: Info,
        status: Optional[TicketStatusEnum] = None,
        search: Optional[str] = None,
        first: int = 50,
        after: Optional[str] = None,
    ) -> TicketConnection:
        """Get all tickets for an event (paginated)."""
        tq = ticket_queries.TicketManagementQueries()
        return await tq.eventTickets(info, str(eventId), status, search, first, after)

    @strawberry.field
    async def ticketByCode(
        self, eventId: strawberry.ID, ticketCode: str, info: Info
    ) -> Optional[TicketGQLType]:
        """Get a ticket by its code (for check-in)."""
        tq = ticket_queries.TicketManagementQueries()
        return await tq.ticketByCode(info, str(eventId), ticketCode)

    @strawberry.field
    async def ticket(
        self, id: strawberry.ID, info: Info
    ) -> Optional[TicketGQLType]:
        """Get a single ticket by ID."""
        tq = ticket_queries.TicketManagementQueries()
        return await tq.ticket(info, str(id))

    @strawberry.field
    async def myTickets(
        self, info: Info, eventId: Optional[strawberry.ID] = None
    ) -> List[TicketGQLType]:
        """Get current user's tickets."""
        tq = ticket_queries.TicketManagementQueries()
        event_id_str = str(eventId) if eventId else None
        return await tq.myTickets(info, event_id_str)

    @strawberry.field
    async def checkInStats(
        self, eventId: strawberry.ID, info: Info
    ) -> CheckInStatsType:
        """Get check-in statistics for an event."""
        tq = ticket_queries.TicketManagementQueries()
        return await tq.checkInStats(info, str(eventId))

    # --- MONETIZATION QUERIES ---

    @strawberry.field
    def eventAds(self, eventId: strawberry.ID, info: Info) -> typing.List[AdType]:
        """Get all ads for a specific event."""
        db = info.context.db
        user = info.context.user
        if not user or not user.get("orgId"):
            raise HTTPException(status_code=403, detail="Not authorized")
        return crud.ad.get_multi_by_event(db, event_id=str(eventId))

    @strawberry.field
    def eventOffers(self, eventId: strawberry.ID, info: Info) -> typing.List[OfferType]:
        """Get all upsell offers for a specific event (organizer only)."""
        db = info.context.db
        user = info.context.user
        if not user or not user.get("orgId"):
            raise HTTPException(status_code=403, detail="Not authorized")
        return crud.offer.get_multi_by_event(db, event_id=str(eventId))

    @strawberry.field
    def activeOffers(
        self,
        eventId: strawberry.ID,
        info: Info,
        sessionId: typing.Optional[strawberry.ID] = None,
        placement: typing.Optional[str] = None
    ) -> typing.List[OfferType]:
        """
        Get active offers for an event (attendee/public view).
        Returns only offers that are:
        - Active and not archived
        - Within their start/expiration window
        - Have available inventory
        - Match targeting rules (if sessionId provided)
        """
        db = info.context.db
        user = info.context.user

        # Require authentication for viewing offers
        if not user or not user.get("sub"):
            raise HTTPException(status_code=401, detail="Authentication required")

        # Verify event exists and is accessible
        event = crud.event.get(db, id=str(eventId))
        if not event:
            raise HTTPException(status_code=404, detail="Event not found")

        # Check if user has access to this event (either public or registered)
        can_access = False
        if event.is_public and not event.is_archived:
            can_access = True
        else:
            # Check if user is registered
            from ..models.registration import Registration
            registration = (
                db.query(Registration)
                .filter(
                    Registration.event_id == str(eventId),
                    Registration.user_id == user["sub"],
                    Registration.is_archived == "false",
                    Registration.status != "cancelled",
                )
                .first()
            )
            if registration:
                can_access = True

        if not can_access:
            raise HTTPException(status_code=403, detail="Not authorized to view this event's offers")

        # Get active offers
        session_id_str = str(sessionId) if sessionId else None
        return crud.offer.get_active_offers(
            db,
            event_id=str(eventId),
            placement=placement,
            session_id=session_id_str
        )

    # --- WAITLIST QUERIES ---

    @strawberry.field
    def my_waitlist_position(
        self, session_id: strawberry.ID, info: Info
    ) -> Optional[WaitlistPositionType]:
        """Get current user's position in waitlist for a session."""
        wq = WaitlistQuery()
        return wq.my_waitlist_position(session_id, info)

    @strawberry.field
    def my_waitlist_entry(
        self, session_id: strawberry.ID, info: Info
    ) -> Optional[WaitlistEntryType]:
        """Get current user's waitlist entry for a session."""
        wq = WaitlistQuery()
        return wq.my_waitlist_entry(session_id, info)

    @strawberry.field
    def my_waitlist_entries(self, info: Info) -> List[WaitlistEntryType]:
        """Get all waitlist entries for current user."""
        wq = WaitlistQuery()
        return wq.my_waitlist_entries(info)

    @strawberry.field
    def session_capacity(
        self, session_id: strawberry.ID, info: Info
    ) -> SessionCapacityType:
        """Get capacity information for a session (public)."""
        wq = WaitlistQuery()
        return wq.session_capacity(session_id, info)

    @strawberry.field
    def session_waitlist(
        self,
        session_id: strawberry.ID,
        status_filter: Optional[str] = None,
        info: Info = None
    ) -> List[WaitlistEntryType]:
        """[ADMIN] Get all waitlist entries for a session."""
        wq = WaitlistQuery()
        return wq.session_waitlist(session_id, status_filter, info)

    @strawberry.field
    def session_waitlist_stats(
        self, session_id: strawberry.ID, info: Info
    ) -> WaitlistStatsType:
        """[ADMIN] Get waitlist statistics for a session."""
        wq = WaitlistQuery()
        return wq.session_waitlist_stats(session_id, info)

    @strawberry.field
    def event_waitlist_analytics(
        self,
        event_id: strawberry.ID,
        use_cache: bool = True,
        info: Info = None
    ) -> EventWaitlistAnalyticsType:
        """[ADMIN] Get comprehensive waitlist analytics for an event."""
        wq = WaitlistQuery()
        return wq.event_waitlist_analytics(event_id, use_cache, info)