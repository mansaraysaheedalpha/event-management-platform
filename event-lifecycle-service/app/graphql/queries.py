# app/graphql/queries.py
import strawberry
import typing
from typing import List, Optional
from datetime import datetime
from strawberry.types import Info
from fastapi import HTTPException
import httpx
from ..core.config import settings
from .. import crud
from ..utils.security import validate_limit, validate_enum, VALID_PLACEMENTS
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
    OfferPurchaseType,
    DigitalContentType,
    # Platform stats
    PlatformStatsType,
    # Virtual attendance types
    VirtualAttendanceType,
    VirtualAttendanceStatsType,
    EventVirtualAttendanceStatsType,
    # Monetization analytics types
    MonetizationAnalyticsType,
    RevenueAnalyticsType,
    RevenueDayType,
    OffersAnalyticsType,
    OfferPerformerType,
    AdsAnalyticsType,
    AdPerformerType,
    WaitlistAnalyticsSummaryType,
)
from .rsvp_types import (
    MyScheduleSessionType,
    RsvpStatus,
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
from . import admin_queries
from . import connect_queries
from .admin_types import (
    AdminDashboardStats,
    AdminOrganizationSummary,
    PaginatedAdminOrganizations,
    AdminOrganizationDetail,
    AdminTransaction,
    PaginatedTransactions,
    RevenueDataPoint,
    RevenueReport,
    ReportPeriod,
    StripeConnectionStatus,
)
from .connect_types import (
    OrganizationPaymentStatus,
    AccountBalance,
    FeeConfiguration,
)
from .waitlist_types import (
    WaitlistEntryType,
    WaitlistPositionType,
    SessionCapacityType,
    WaitlistStatsType,
    EventWaitlistAnalyticsType,
)
from .waitlist_queries import WaitlistQuery
from .sponsor_queries import SponsorQueries
from .sponsor_types import (
    SponsorTierType,
    SponsorType,
    SponsorWithTierType,
    SponsorUserType,
    SponsorInvitationType,
    SponsorLeadType,
    SponsorStatsType,
    SponsorsListResponse,
)


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
    def session(self, id: strawberry.ID, info: Info) -> Optional[SessionType]:
        """
        Get a single session by ID.
        Accessible to organizers, speakers assigned to the session, and registered attendees.
        """
        user = info.context.user
        if not user or not user.get("sub"):
            raise HTTPException(status_code=401, detail="Authentication required")

        db = info.context.db
        user_id = user["sub"]
        user_org_id = user.get("orgId")

        session_obj = crud.session.get(db, id=str(id))
        if not session_obj:
            return None

        # Get the event to verify access
        event = crud.event.get(db, id=session_obj.event_id)
        if not event:
            return None

        # Check access permissions
        can_access = False

        # Case 1: User is an organizer in the same organization
        if user_org_id and event.organization_id == user_org_id:
            can_access = True
        # Case 2: User is a speaker for this session
        elif any(s.user_id == user_id for s in session_obj.speakers):
            can_access = True
        # Case 3: User is registered for the event
        else:
            registration = crud.registration.get_by_user_or_email(
                db, event_id=session_obj.event_id, user_id=user_id
            )
            if registration:
                can_access = True

        if not can_access:
            return None

        return session_obj

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
    def eventAttendees(
        self, eventId: strawberry.ID, info: Info
    ) -> List[RegistrationType]:
        """
        Returns all attendees for an event. Accessible to any registered attendee.
        This is used for the DM feature to show other attendees.
        Only returns attendees with user accounts (not guest registrations).
        """
        user = info.context.user
        if not user or not user.get("sub"):
            raise HTTPException(status_code=401, detail="Authentication required")

        db = info.context.db
        user_id = user["sub"]

        # Verify the user is registered for this event
        user_registration = crud.registration.get_by_user_or_email(
            db, event_id=str(eventId), user_id=user_id
        )
        if not user_registration:
            raise HTTPException(
                status_code=403,
                detail="You must be registered for this event to see other attendees"
            )

        # Get all registrations for this event (only those with user_id, not guest registrations)
        registrations = crud.registration.get_multi_by_event(db, event_id=str(eventId))

        # Filter to only include registrations with user accounts
        return [r for r in registrations if r.user_id]

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

    @strawberry.field
    def adsForContext(
        self,
        eventId: strawberry.ID,
        placement: str,
        info: Info,
        sessionId: typing.Optional[strawberry.ID] = None,
        limit: typing.Optional[int] = 10
    ) -> typing.List[AdType]:
        """
        Get ads for a specific context/placement (attendee view).
        Returns ads that are:
        - Active and not archived
        - Within their scheduling window
        - Targeting the specified placement
        - Targeting the session (if provided)
        """
        db = info.context.db

        # SECURITY: Validate placement enum
        valid, err = validate_enum(placement, "placement", VALID_PLACEMENTS)
        if not valid:
            raise HTTPException(status_code=400, detail=err)

        # SECURITY: Sanitize limit to prevent DoS
        safe_limit = validate_limit(limit, default=10)

        # SECURITY: Verify event exists and is accessible
        event = crud.event.get(db, id=str(eventId))
        if not event:
            raise HTTPException(status_code=404, detail="Event not found")

        # Only show ads for public or active events
        if event.is_archived:
            return []

        # Use the optimized CRUD method that pushes all filtering into SQL
        # (active, not archived, scheduling window, placement, session targeting)
        ads = crud.ad.get_active_ads(
            db,
            event_id=str(eventId),
            placement=placement,
            session_id=str(sessionId) if sessionId else None
        )

        # Sort by weight (higher weight = more likely to be shown)
        ads.sort(key=lambda x: x.weight or 1, reverse=True)

        # Apply sanitized limit
        return ads[:safe_limit]

    @strawberry.field
    def myPurchasedOffers(
        self, eventId: strawberry.ID, info: Info
    ) -> typing.List["OfferPurchaseType"]:
        """
        Get current user's purchased offers for an event.
        """
        db = info.context.db
        user = info.context.user

        if not user or not user.get("sub"):
            raise HTTPException(status_code=401, detail="Authentication required")

        user_id = user["sub"]

        # Get user's purchases for this event
        purchases = crud.offer_purchase.get_user_purchases(
            db,
            user_id=user_id,
            event_id=str(eventId)
        )

        # Batch-load all offers in one query instead of N+1
        offer_ids = [p.offer_id for p in purchases]
        from app.models.offer import Offer
        offers = db.query(Offer).filter(Offer.id.in_(offer_ids)).all()
        offer_map = {o.id: o for o in offers}

        # Convert to response type
        result = []
        for purchase in purchases:
            offer = offer_map.get(purchase.offer_id)
            result.append(OfferPurchaseType(
                id=purchase.id,
                offer=offer,
                quantity=purchase.quantity,
                unitPrice=purchase.unit_price,
                totalPrice=purchase.total_price,
                currency=purchase.currency,
                fulfillmentStatus=purchase.fulfillment_status,
                fulfillmentType=purchase.fulfillment_type,
                digitalContent=DigitalContentType(
                    downloadUrl=purchase.digital_content_url,
                    accessCode=purchase.access_code
                ) if purchase.digital_content_url or purchase.access_code else None,
                trackingNumber=purchase.tracking_number,
                purchasedAt=purchase.purchased_at.isoformat() if purchase.purchased_at else None,
                fulfilledAt=purchase.fulfilled_at.isoformat() if purchase.fulfilled_at else None
            ))

        return result

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

    @strawberry.field
    def monetization_analytics(
        self,
        event_id: strawberry.ID,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        include_archived: bool = False,  # Include archived ads in analytics
        info: Info = None
    ) -> MonetizationAnalyticsType:
        """
        [ADMIN] Get comprehensive monetization analytics for an event.
        Includes revenue, offers, ads, and waitlist metrics.

        Args:
            include_archived: If True, includes metrics from archived/deleted ads
                            in the totals and lists. Default is False (active only).
        """
        user = info.context.user
        if not user:
            raise HTTPException(status_code=401, detail="Authentication required")

        db = info.context.db
        event_id_str = str(event_id)

        # Verify event exists and user has access
        from ..models.event import Event as EventModel
        event = db.query(EventModel).filter(EventModel.id == event_id_str).first()
        if not event:
            raise HTTPException(status_code=404, detail="Event not found")

        user_id = user.get("sub")
        user_org_id = user.get("orgId")

        if event.owner_id != user_id and (not user_org_id or event.organization_id != user_org_id):
            raise HTTPException(status_code=403, detail="Not authorized")

        # Import models
        from ..models.ad import Ad
        from ..models.ad_event import AdEvent
        from ..models.offer import Offer
        from ..models.offer_purchase import OfferPurchase
        from ..models.session_waitlist import SessionWaitlist
        from sqlalchemy import func, case

        # --- Revenue Analytics ---
        # Get offer revenue (join with Offer to filter by event_id)
        offer_revenue = db.query(func.coalesce(func.sum(OfferPurchase.total_price), 0)).join(
            Offer, Offer.id == OfferPurchase.offer_id
        ).filter(
            Offer.event_id == event_id_str
        ).scalar() or 0

        # Ads don't typically generate direct revenue in this system (they're sponsor placements)
        # Set to 0 for now
        ads_revenue = 0

        total_revenue = float(offer_revenue) + float(ads_revenue)

        # Revenue by day (last 30 days) - simplified
        revenue_by_day = []

        revenue = RevenueAnalyticsType(
            total=total_revenue,
            fromOffers=float(offer_revenue),
            fromAds=float(ads_revenue),
            byDay=revenue_by_day
        )

        # --- Offers Analytics ---
        total_offer_purchases = db.query(func.count(OfferPurchase.id)).join(
            Offer, Offer.id == OfferPurchase.offer_id
        ).filter(
            Offer.event_id == event_id_str
        ).scalar() or 0

        # Calculate conversion rate (purchases / views) - simplified since we don't track views
        offer_conversion_rate = 0.0
        avg_order_value = 0.0
        if total_offer_purchases > 0:
            avg_order_value = float(offer_revenue) / total_offer_purchases

        # Top performing offers
        top_offers_query = db.query(
            Offer.id,
            Offer.title,
            func.coalesce(func.sum(OfferPurchase.total_price), 0).label('revenue'),
            func.count(OfferPurchase.id).label('conversions')
        ).outerjoin(OfferPurchase, OfferPurchase.offer_id == Offer.id).filter(
            Offer.event_id == event_id_str
        ).group_by(Offer.id).order_by(func.sum(OfferPurchase.total_price).desc()).limit(5).all()

        top_offers = [
            OfferPerformerType(
                offerId=str(o.id),
                title=o.title or "Untitled",
                revenue=float(o.revenue or 0),
                conversions=int(o.conversions or 0)
            )
            for o in top_offers_query
        ]

        offers = OffersAnalyticsType(
            totalViews=0,  # Not tracked
            totalPurchases=total_offer_purchases,
            conversionRate=offer_conversion_rate,
            averageOrderValue=avg_order_value,
            topPerformers=top_offers
        )

        # --- Ads Analytics ---
        # Enhanced analytics with per-ad breakdown and historical data support

        # Count active and archived ads for this event
        active_ads_count = db.query(func.count(Ad.id)).filter(
            Ad.event_id == event_id_str,
            Ad.is_archived.is_(False)
        ).scalar() or 0

        archived_ads_count = db.query(func.count(Ad.id)).filter(
            Ad.event_id == event_id_str,
            Ad.is_archived.is_(True)
        ).scalar() or 0

        # Build base filter for include_archived parameter
        ad_base_filters = [Ad.event_id == event_id_str]
        if not include_archived:
            ad_base_filters.append(Ad.is_archived.is_(False))

        # Count impressions (event_type = 'IMPRESSION')
        total_impressions = db.query(func.count(AdEvent.id)).join(
            Ad, Ad.id == AdEvent.ad_id
        ).filter(
            *ad_base_filters,
            AdEvent.event_type == 'IMPRESSION'
        ).scalar() or 0

        # Count clicks (event_type = 'CLICK')
        total_clicks = db.query(func.count(AdEvent.id)).join(
            Ad, Ad.id == AdEvent.ad_id
        ).filter(
            *ad_base_filters,
            AdEvent.event_type == 'CLICK'
        ).scalar() or 0

        avg_ctr = (total_clicks / total_impressions * 100) if total_impressions > 0 else 0.0

        # Get ALL ads with their individual performance metrics
        all_ads_query = db.query(
            Ad.id,
            Ad.name,
            Ad.content_type,
            Ad.is_archived,
            func.sum(case((AdEvent.event_type == 'IMPRESSION', 1), else_=0)).label('impressions'),
            func.sum(case((AdEvent.event_type == 'CLICK', 1), else_=0)).label('clicks')
        ).outerjoin(AdEvent, AdEvent.ad_id == Ad.id).filter(
            *ad_base_filters
        ).group_by(Ad.id).order_by(
            func.sum(case((AdEvent.event_type == 'CLICK', 1), else_=0)).desc()  # Order by clicks for CTR relevance
        ).limit(100).all()  # M-FE6: Cap unbounded result set

        all_ads_performance = []
        for ad in all_ads_query:
            ad_impressions = int(ad.impressions or 0)
            ad_clicks = int(ad.clicks or 0)
            ad_ctr = (ad_clicks / ad_impressions * 100) if ad_impressions > 0 else 0.0
            all_ads_performance.append(AdPerformerType(
                adId=str(ad.id),
                name=ad.name or "Untitled",
                impressions=ad_impressions,
                clicks=ad_clicks,
                ctr=round(ad_ctr, 2),
                isArchived=ad.is_archived or False,
                contentType=ad.content_type
            ))

        # Top 5 performers (by CTR, excluding zero-impression ads for fairness)
        top_ads = sorted(
            [a for a in all_ads_performance if a.impressions > 0],
            key=lambda x: x.ctr,
            reverse=True
        )[:5]

        ads = AdsAnalyticsType(
            totalImpressions=total_impressions,
            totalClicks=total_clicks,
            averageCTR=round(avg_ctr, 2),
            activeAdsCount=active_ads_count,
            archivedAdsCount=archived_ads_count,
            topPerformers=top_ads,
            allAdsPerformance=all_ads_performance
        )

        # --- Waitlist Analytics ---
        from ..models.session import Session as SessionModel

        session_ids = [str(s.id) for s in db.query(SessionModel.id).filter(
            SessionModel.event_id == event_id_str
        ).all()]

        total_waitlist_joins = db.query(func.count(SessionWaitlist.id)).filter(
            SessionWaitlist.session_id.in_(session_ids)
        ).scalar() or 0

        waitlist_offers_issued = db.query(func.count(SessionWaitlist.id)).filter(
            SessionWaitlist.session_id.in_(session_ids),
            SessionWaitlist.status.in_(['OFFERED', 'ACCEPTED', 'DECLINED', 'EXPIRED'])
        ).scalar() or 0

        waitlist_accepted = db.query(func.count(SessionWaitlist.id)).filter(
            SessionWaitlist.session_id.in_(session_ids),
            SessionWaitlist.status == 'ACCEPTED'
        ).scalar() or 0

        waitlist_acceptance_rate = (waitlist_accepted / waitlist_offers_issued * 100) if waitlist_offers_issued > 0 else 0.0

        waitlist = WaitlistAnalyticsSummaryType(
            totalJoins=total_waitlist_joins,
            offersIssued=waitlist_offers_issued,
            acceptanceRate=round(waitlist_acceptance_rate, 1),
            averageWaitTimeMinutes=0.0  # Would need timestamp tracking to calculate
        )

        return MonetizationAnalyticsType(
            revenue=revenue,
            offers=offers,
            ads=ads,
            waitlist=waitlist
        )

    @strawberry.field
    def platformStats(self, info: Info) -> PlatformStatsType:
        """
        [PUBLIC] Get platform-wide statistics for marketing display.
        No authentication required.
        """
        db = info.context.db

        # Count total events (non-archived)
        total_events = db.query(crud.event.model).filter(
            crud.event.model.is_archived == False
        ).count()

        # Count total registrations (attendees)
        total_attendees = db.query(crud.registration.model).count()

        # Count total organizations
        # Since we don't have org model here, we count distinct org_ids from events
        from sqlalchemy import func
        total_orgs = db.query(
            func.count(func.distinct(crud.event.model.organization_id))
        ).scalar() or 0

        # Uptime is typically monitored externally, so we return a fixed high value
        # In production, this could come from an external monitoring service
        uptime_percentage = 99.9

        return PlatformStatsType(
            totalEvents=total_events,
            totalAttendees=total_attendees,
            totalOrganizations=total_orgs,
            uptimePercentage=uptime_percentage
        )

    # --- SPONSOR QUERIES ---

    @strawberry.field
    def eventSponsorTiers(
        self, eventId: strawberry.ID, info: Info
    ) -> List[SponsorTierType]:
        """Get all sponsor tiers for an event."""
        sq = SponsorQueries()
        return sq.event_sponsor_tiers(str(eventId), info)

    @strawberry.field
    def sponsorTier(
        self, tierId: strawberry.ID, info: Info
    ) -> Optional[SponsorTierType]:
        """Get a single sponsor tier by ID."""
        sq = SponsorQueries()
        return sq.sponsor_tier(str(tierId), info)

    @strawberry.field
    def eventSponsors(
        self,
        eventId: strawberry.ID,
        info: Info,
        includeArchived: bool = False,
        tierId: Optional[strawberry.ID] = None
    ) -> SponsorsListResponse:
        """Get all sponsors for an event."""
        sq = SponsorQueries()
        tier_id_str = str(tierId) if tierId else None
        return sq.event_sponsors(str(eventId), info, includeArchived, tier_id_str)

    @strawberry.field
    def sponsor(
        self, sponsorId: strawberry.ID, info: Info
    ) -> Optional[SponsorType]:
        """Get a single sponsor by ID."""
        sq = SponsorQueries()
        return sq.sponsor(str(sponsorId), info)

    @strawberry.field
    def sponsorWithTier(
        self, sponsorId: strawberry.ID, info: Info
    ) -> Optional[SponsorWithTierType]:
        """Get a sponsor with its tier information."""
        sq = SponsorQueries()
        return sq.sponsor_with_tier(str(sponsorId), info)

    @strawberry.field
    def mySponsors(self, info: Info) -> List[SponsorType]:
        """Get sponsors where the current user is a team member."""
        sq = SponsorQueries()
        return sq.my_sponsors(info)

    @strawberry.field
    def sponsorUsers(
        self, sponsorId: strawberry.ID, info: Info
    ) -> List[SponsorUserType]:
        """Get all users for a sponsor."""
        sq = SponsorQueries()
        return sq.sponsor_users(str(sponsorId), info)

    @strawberry.field
    def mySponsorMembership(
        self, sponsorId: strawberry.ID, info: Info
    ) -> Optional[SponsorUserType]:
        """Get the current user's membership for a sponsor."""
        sq = SponsorQueries()
        return sq.my_sponsor_membership(str(sponsorId), info)

    @strawberry.field
    def sponsorInvitations(
        self,
        sponsorId: strawberry.ID,
        info: Info,
        status: Optional[str] = None
    ) -> List[SponsorInvitationType]:
        """Get all invitations for a sponsor."""
        sq = SponsorQueries()
        return sq.sponsor_invitations(str(sponsorId), info, status)

    @strawberry.field
    def validateSponsorInvitation(
        self, token: str, info: Info
    ) -> Optional[SponsorInvitationType]:
        """Validate an invitation token and return invitation details."""
        sq = SponsorQueries()
        return sq.validate_sponsor_invitation(token, info)

    @strawberry.field
    def sponsorLeads(
        self,
        sponsorId: strawberry.ID,
        info: Info,
        intentLevel: Optional[str] = None,
        followUpStatus: Optional[str] = None,
        isStarred: Optional[bool] = None,
        includeArchived: bool = False,
        limit: int = 100,
        offset: int = 0
    ) -> List[SponsorLeadType]:
        """Get leads for a sponsor."""
        sq = SponsorQueries()
        return sq.sponsor_leads(
            str(sponsorId), info,
            intent_level=intentLevel,
            follow_up_status=followUpStatus,
            is_starred=isStarred,
            include_archived=includeArchived,
            limit=limit,
            offset=offset
        )

    @strawberry.field
    def sponsorLead(
        self, leadId: strawberry.ID, info: Info
    ) -> Optional[SponsorLeadType]:
        """Get a single lead by ID."""
        sq = SponsorQueries()
        return sq.sponsor_lead(str(leadId), info)

    @strawberry.field
    def sponsorStats(
        self, sponsorId: strawberry.ID, info: Info
    ) -> SponsorStatsType:
        """Get statistics for a sponsor's leads."""
        sq = SponsorQueries()
        return sq.sponsor_stats(str(sponsorId), info)

    @strawberry.field
    def publicEventSponsors(
        self, eventId: strawberry.ID, info: Info
    ) -> List[SponsorType]:
        """Get public sponsor list for an event (attendee view)."""
        sq = SponsorQueries()
        return sq.public_event_sponsors(str(eventId), info)

    @strawberry.field
    def publicSponsor(
        self, sponsorId: strawberry.ID, info: Info
    ) -> Optional[SponsorType]:
        """Get public sponsor details (attendee view)."""
        sq = SponsorQueries()
        return sq.public_sponsor(str(sponsorId), info)

    # --- VIRTUAL ATTENDANCE QUERIES ---

    @strawberry.field
    def virtualAttendanceStats(
        self, sessionId: strawberry.ID, info: Info
    ) -> VirtualAttendanceStatsType:
        """
        Get virtual attendance statistics for a session.
        Available to organizers and registered attendees.
        """
        user = info.context.user
        if not user or not user.get("sub"):
            raise HTTPException(status_code=401, detail="Authentication required")

        db = info.context.db
        user_id = user["sub"]
        user_org_id = user.get("orgId")

        # Get the session
        session = crud.session.get(db, id=str(sessionId))
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")

        # Get the event to verify access
        event = crud.event.get(db, id=session.event_id)
        if not event:
            raise HTTPException(status_code=404, detail="Event not found")

        # Check if user is organizer or registered attendee
        is_organizer = user_org_id and event.organization_id == user_org_id
        if not is_organizer:
            # Check if user is registered for the event
            registration = crud.registration.get_by_user_or_email(
                db, event_id=session.event_id, user_id=user_id
            )
            if not registration:
                raise HTTPException(
                    status_code=403,
                    detail="You must be registered for this event to view attendance stats"
                )

        # Get stats from CRUD
        stats = crud.virtual_attendance.get_session_stats(db, session_id=str(sessionId))

        return VirtualAttendanceStatsType(
            sessionId=str(sessionId),
            totalViews=stats["total_views"],
            uniqueViewers=stats["unique_viewers"],
            currentViewers=stats["current_viewers"],
            avgWatchDurationSeconds=stats["avg_watch_duration_seconds"],
            peakViewers=stats.get("peak_viewers", stats["current_viewers"]),
        )

    @strawberry.field
    def eventVirtualAttendanceStats(
        self, eventId: strawberry.ID, info: Info
    ) -> EventVirtualAttendanceStatsType:
        """
        Get virtual attendance statistics for an entire event.
        Available to organizers only.
        """
        user = info.context.user
        if not user or not user.get("orgId"):
            raise HTTPException(status_code=403, detail="Not authorized")

        db = info.context.db
        org_id = user["orgId"]

        # Verify event belongs to org
        event = crud.event.get(db, id=str(eventId))
        if not event or event.organization_id != org_id:
            raise HTTPException(status_code=404, detail="Event not found")

        # Get event-level stats
        event_stats = crud.virtual_attendance.get_event_stats(db, event_id=str(eventId))

        # Get per-session stats — batched to avoid N+1
        sessions = crud.session.get_multi_by_event(db, event_id=str(eventId))
        session_ids = [s.id for s in sessions]

        # Batch aggregation: 1 query for all sessions instead of N
        from app.models.virtual_attendance import VirtualAttendance
        from sqlalchemy import func as sa_func

        batch_stats = (
            db.query(
                VirtualAttendance.session_id,
                sa_func.count(VirtualAttendance.id).label("total_views"),
                sa_func.count(sa_func.distinct(VirtualAttendance.user_id)).label("unique_viewers"),
                sa_func.avg(VirtualAttendance.watch_duration_seconds).label("avg_duration"),
            )
            .filter(VirtualAttendance.session_id.in_(session_ids))
            .group_by(VirtualAttendance.session_id)
            .all()
        )
        stats_map = {
            row.session_id: {
                "total_views": row.total_views,
                "unique_viewers": row.unique_viewers,
                "avg_duration": float(row.avg_duration or 0),
            }
            for row in batch_stats
        }

        # Active viewers per session (separate query, still batched)
        active_stats = (
            db.query(
                VirtualAttendance.session_id,
                sa_func.count(VirtualAttendance.id).label("active"),
            )
            .filter(
                VirtualAttendance.session_id.in_(session_ids),
                VirtualAttendance.left_at.is_(None),
            )
            .group_by(VirtualAttendance.session_id)
            .all()
        )
        active_map = {row.session_id: row.active for row in active_stats}

        session_stats = []
        for session in sessions:
            s = stats_map.get(session.id, {})
            session_stats.append(VirtualAttendanceStatsType(
                sessionId=session.id,
                totalViews=s.get("total_views", 0),
                uniqueViewers=s.get("unique_viewers", 0),
                currentViewers=active_map.get(session.id, 0),
                avgWatchDurationSeconds=s.get("avg_duration", 0),
                peakViewers=active_map.get(session.id, 0),
            ))

        return EventVirtualAttendanceStatsType(
            eventId=str(eventId),
            totalViews=event_stats["total_views"],
            uniqueViewers=event_stats["unique_viewers"],
            currentViewers=event_stats["current_viewers"],
            avgWatchDurationSeconds=event_stats["avg_watch_duration_seconds"],
            sessionStats=session_stats,
        )

    @strawberry.field
    def myVirtualAttendance(
        self, eventId: strawberry.ID, info: Info
    ) -> typing.List[VirtualAttendanceType]:
        """
        Get the current user's virtual attendance records for an event.
        Useful for showing watch history.
        """
        user = info.context.user
        if not user or not user.get("sub"):
            raise HTTPException(status_code=401, detail="Authentication required")

        db = info.context.db
        user_id = user["sub"]

        # Get user's attendance records for this event
        records = crud.virtual_attendance.get_user_event_attendance(
            db, user_id=user_id, event_id=str(eventId)
        )

        return [
            VirtualAttendanceType(
                id=r.id,
                userId=r.user_id,
                sessionId=r.session_id,
                eventId=r.event_id,
                joinedAt=r.joined_at,
                leftAt=r.left_at,
                watchDurationSeconds=r.watch_duration_seconds,
                deviceType=r.device_type,
            )
            for r in records
        ]

    # --- SESSION RSVP QUERIES ---

    @strawberry.field
    def mySchedule(
        self, eventId: strawberry.ID, info: Info
    ) -> List[MyScheduleSessionType]:
        """
        Get current user's RSVPed sessions for an event (their personal schedule).
        Sorted by session start time.
        """
        user = info.context.user
        if not user or not user.get("sub"):
            raise HTTPException(status_code=401, detail="Authentication required")

        db = info.context.db
        user_id = user["sub"]

        from app.crud.crud_session_rsvp import session_rsvp as session_rsvp_crud
        from app.models.session import Session as SessionModel

        rsvps = session_rsvp_crud.get_rsvps_by_user(
            db, user_id=user_id, event_id=str(eventId)
        )

        if not rsvps:
            return []

        # Batch-load all sessions in one query
        session_ids = [r.session_id for r in rsvps]
        sessions = db.query(SessionModel).filter(
            SessionModel.id.in_(session_ids)
        ).all()
        session_map = {s.id: s for s in sessions}

        result = []
        for rsvp in rsvps:
            session_obj = session_map.get(rsvp.session_id)
            if not session_obj:
                continue
            speaker_names = ", ".join(
                s.name for s in (session_obj.speakers or [])
            )
            result.append(MyScheduleSessionType(
                rsvp_id=rsvp.id,
                rsvp_status=RsvpStatus[rsvp.status],
                rsvp_at=rsvp.rsvp_at,
                session_id=session_obj.id,
                title=session_obj.title,
                start_time=session_obj.start_time,
                end_time=session_obj.end_time,
                session_type=getattr(session_obj, "session_type", None),
                speakers=speaker_names or None,
            ))

        # Sort by session start time
        result.sort(key=lambda x: x.start_time)
        return result

    # --- PLATFORM ADMIN QUERIES ---

    @strawberry.field
    def adminDashboardStats(self, info: Info) -> AdminDashboardStats:
        """
        [PLATFORM ADMIN] Get platform-wide dashboard statistics.
        Includes total revenue, GMV, organization counts, ticket sales.
        """
        return admin_queries.get_admin_dashboard_stats(info)

    @strawberry.field
    def adminOrganizations(
        self,
        info: Info,
        page: int = 1,
        limit: int = 20,
        search: typing.Optional[str] = None,
        stripeStatus: typing.Optional[StripeConnectionStatus] = None,
    ) -> PaginatedAdminOrganizations:
        """
        [PLATFORM ADMIN] Get paginated list of all organizations with Stripe status.
        """
        return admin_queries.get_admin_organizations(
            info, page, limit, search, stripeStatus
        )

    @strawberry.field
    def adminOrganizationDetail(
        self, organizationId: strawberry.ID, info: Info
    ) -> AdminOrganizationDetail:
        """
        [PLATFORM ADMIN] Get detailed information about a specific organization.
        """
        return admin_queries.get_admin_organization_detail(str(organizationId), info)

    @strawberry.field
    def adminTransactions(
        self,
        info: Info,
        page: int = 1,
        limit: int = 20,
        organizationId: typing.Optional[str] = None,
        dateFrom: typing.Optional[datetime] = None,
        dateTo: typing.Optional[datetime] = None,
        status: typing.Optional[str] = None,
    ) -> PaginatedTransactions:
        """
        [PLATFORM ADMIN] Get paginated list of all transactions across the platform.
        """
        from datetime import datetime as dt
        return admin_queries.get_admin_transactions(
            info, page, limit, organizationId, dateFrom, dateTo, status
        )

    @strawberry.field
    def adminRevenueReport(
        self,
        period: ReportPeriod,
        dateFrom: datetime,
        dateTo: datetime,
        info: Info,
    ) -> RevenueReport:
        """
        [PLATFORM ADMIN] Get revenue report aggregated by period.
        """
        return admin_queries.get_admin_revenue_report(info, period, dateFrom, dateTo)

    # --- STRIPE CONNECT QUERIES ---

    @strawberry.field
    async def organizationPaymentStatus(
        self, organizationId: str, info: Info
    ) -> OrganizationPaymentStatus:
        """
        Get organization's Stripe Connect onboarding and account status.
        Auth: OWNER or ADMIN of the organization.
        """
        return await connect_queries.get_organization_payment_status(organizationId, info)

    @strawberry.field
    async def organizationBalance(
        self, organizationId: str, info: Info
    ) -> AccountBalance:
        """
        Get connected account balance (available and pending).
        Auth: OWNER or ADMIN of the organization.
        """
        return await connect_queries.get_organization_balance(organizationId, info)

    @strawberry.field
    def organizationFees(
        self, organizationId: str, info: Info
    ) -> FeeConfiguration:
        """
        Get platform fee configuration for an organization.
        Auth: OWNER or ADMIN of the organization.
        """
        return connect_queries.get_organization_fees(organizationId, info)