# app/crud/crud_dashboard.py
"""
CRUD operations for dashboard statistics.
Provides aggregated metrics for the organizer dashboard.
"""
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import func, distinct, and_, cast, Date
from typing import List, Dict, Any
from app.models.event import Event
from app.models.registration import Registration
from app.models.session import Session as SessionModel


class CRUDDashboard:
    """
    Dashboard statistics operations.
    All methods are scoped to a specific organization.
    """

    def get_total_attendees(self, db: Session, *, org_id: str) -> int:
        """
        Counts total registrations (attendees) across all organization events.
        Includes both user-based registrations and guest registrations.
        """
        return (
            db.query(func.count(Registration.id))
            .join(Event, Event.id == Registration.event_id)
            .filter(
                Event.organization_id == org_id,
                Event.is_archived == False,
                Registration.is_archived == "false",
                Registration.status != "cancelled",
            )
            .scalar() or 0
        )

    def get_total_registrations(self, db: Session, *, org_id: str) -> int:
        """
        Counts total registrations (including guests) across all organization events.
        """
        return (
            db.query(func.count(Registration.id))
            .join(Event, Event.id == Registration.event_id)
            .filter(
                Event.organization_id == org_id,
                Event.is_archived == False,
                Registration.is_archived == "false",
                Registration.status != "cancelled",
            )
            .scalar() or 0
        )

    def get_active_sessions_count(self, db: Session, *, org_id: str) -> int:
        """
        Counts currently active sessions (start_time <= now <= end_time).
        Sessions must belong to non-archived events in the organization.
        """
        now = datetime.utcnow()
        return (
            db.query(func.count(SessionModel.id))
            .join(Event, Event.id == SessionModel.event_id)
            .filter(
                Event.organization_id == org_id,
                Event.is_archived == False,
                SessionModel.is_archived == False,
                SessionModel.start_time <= now,
                SessionModel.end_time >= now,
            )
            .scalar() or 0
        )

    def get_total_events(self, db: Session, *, org_id: str) -> int:
        """
        Counts total non-archived events for the organization.
        """
        return (
            db.query(func.count(Event.id))
            .filter(
                Event.organization_id == org_id,
                Event.is_archived == False,
            )
            .scalar() or 0
        )

    def get_weekly_attendance(
        self, db: Session, *, org_id: str, days: int = 7
    ) -> List[Dict[str, Any]]:
        """
        Gets daily attendance data for the last N days.
        Shows registrations for events starting on each day.
        Falls back to upcoming events if no recent activity.
        Returns a list of {label, date, value} for chart display.
        """
        today = datetime.utcnow().date()
        end_date = today
        start_date = end_date - timedelta(days=days - 1)

        # First try to get check-in data (if available)
        checkin_counts = (
            db.query(
                cast(Registration.checked_in_at, Date).label("date"),
                func.count(Registration.id).label("count"),
            )
            .join(Event, Event.id == Registration.event_id)
            .filter(
                Event.organization_id == org_id,
                Event.is_archived == False,
                Registration.is_archived == "false",
                Registration.status != "cancelled",
                Registration.checked_in_at.isnot(None),
                cast(Registration.checked_in_at, Date) >= start_date,
                cast(Registration.checked_in_at, Date) <= end_date,
            )
            .group_by(cast(Registration.checked_in_at, Date))
            .all()
        )

        daily_counts = checkin_counts

        # If no check-in data, try event start dates in the past week
        if not daily_counts:
            daily_counts = (
                db.query(
                    cast(Event.start_date, Date).label("date"),
                    func.count(Registration.id).label("count"),
                )
                .join(Event, Event.id == Registration.event_id)
                .filter(
                    Event.organization_id == org_id,
                    Event.is_archived == False,
                    Registration.is_archived == "false",
                    Registration.status != "cancelled",
                    cast(Event.start_date, Date) >= start_date,
                    cast(Event.start_date, Date) <= end_date,
                )
                .group_by(cast(Event.start_date, Date))
                .all()
            )

        # If still no data, try upcoming events in next 7 days
        if not daily_counts:
            future_end = today + timedelta(days=days)
            daily_counts = (
                db.query(
                    cast(Event.start_date, Date).label("date"),
                    func.count(Registration.id).label("count"),
                )
                .join(Event, Event.id == Registration.event_id)
                .filter(
                    Event.organization_id == org_id,
                    Event.is_archived == False,
                    Registration.is_archived == "false",
                    Registration.status != "cancelled",
                    cast(Event.start_date, Date) >= today,
                    cast(Event.start_date, Date) <= future_end,
                )
                .group_by(cast(Event.start_date, Date))
                .all()
            )
            # If we found upcoming data, shift the date window to show it
            if daily_counts:
                start_date = today
                end_date = future_end

        # Create a map of date -> count
        counts_map = {str(row.date): row.count for row in daily_counts}

        # Generate all dates in range with proper labels
        result = []
        day_names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

        for i in range(days):
            current_date = start_date + timedelta(days=i)
            date_str = str(current_date)
            result.append({
                "label": day_names[current_date.weekday()],
                "date": date_str,
                "value": counts_map.get(date_str, 0),
            })

        return result

    def get_registration_trend(
        self, db: Session, *, org_id: str, periods: int = 12
    ) -> List[Dict[str, Any]]:
        """
        Gets registration trend for the last N periods (days).
        Uses event start dates to show activity distribution.
        Falls back to upcoming events if no recent activity.
        Used for sparkline/trend visualization.
        """
        today = datetime.utcnow().date()
        end_date = today
        start_date = end_date - timedelta(days=periods - 1)

        # First try check-in data
        checkin_counts = (
            db.query(
                cast(Registration.checked_in_at, Date).label("date"),
                func.count(Registration.id).label("count"),
            )
            .join(Event, Event.id == Registration.event_id)
            .filter(
                Event.organization_id == org_id,
                Event.is_archived == False,
                Registration.is_archived == "false",
                Registration.status != "cancelled",
                Registration.checked_in_at.isnot(None),
                cast(Registration.checked_in_at, Date) >= start_date,
                cast(Registration.checked_in_at, Date) <= end_date,
            )
            .group_by(cast(Registration.checked_in_at, Date))
            .all()
        )

        daily_counts = checkin_counts

        # If no check-in data, try past event start dates
        if not daily_counts:
            daily_counts = (
                db.query(
                    cast(Event.start_date, Date).label("date"),
                    func.count(Registration.id).label("count"),
                )
                .join(Event, Event.id == Registration.event_id)
                .filter(
                    Event.organization_id == org_id,
                    Event.is_archived == False,
                    Registration.is_archived == "false",
                    Registration.status != "cancelled",
                    cast(Event.start_date, Date) >= start_date,
                    cast(Event.start_date, Date) <= end_date,
                )
                .group_by(cast(Event.start_date, Date))
                .all()
            )

        # If still no data, try upcoming events
        if not daily_counts:
            future_end = today + timedelta(days=periods)
            daily_counts = (
                db.query(
                    cast(Event.start_date, Date).label("date"),
                    func.count(Registration.id).label("count"),
                )
                .join(Event, Event.id == Registration.event_id)
                .filter(
                    Event.organization_id == org_id,
                    Event.is_archived == False,
                    Registration.is_archived == "false",
                    Registration.status != "cancelled",
                    cast(Event.start_date, Date) >= today,
                    cast(Event.start_date, Date) <= future_end,
                )
                .group_by(cast(Event.start_date, Date))
                .all()
            )
            if daily_counts:
                start_date = today
                end_date = future_end

        # Create a map of date -> count
        counts_map = {str(row.date): row.count for row in daily_counts}

        # Find max for normalization
        max_count = max([row.count for row in daily_counts], default=1) or 1

        # Generate all dates in range
        result = []
        for i in range(periods):
            current_date = start_date + timedelta(days=i)
            date_str = str(current_date)
            count = counts_map.get(date_str, 0)
            # Normalize to 0-100 scale for sparkline
            normalized_value = (count / max_count) * 100 if max_count > 0 else 0
            result.append({
                "period": date_str,
                "value": round(normalized_value, 1),
            })

        return result

    def get_dashboard_stats(self, db: Session, *, org_id: str) -> Dict[str, Any]:
        """
        Gets all dashboard stats in a single call.
        Optimized to minimize database queries.
        """
        now = datetime.utcnow()

        # Get counts using efficient queries
        total_attendees = self.get_total_attendees(db, org_id=org_id)
        active_sessions = self.get_active_sessions_count(db, org_id=org_id)
        total_events = self.get_total_events(db, org_id=org_id)

        # Calculate average engagement rate
        # For now, use a baseline calculation based on check-ins vs registrations
        total_registrations = self.get_total_registrations(db, org_id=org_id)
        checked_in_count = (
            db.query(func.count(Registration.id))
            .join(Event, Event.id == Registration.event_id)
            .filter(
                Event.organization_id == org_id,
                Event.is_archived == False,
                Registration.is_archived == "false",
                Registration.status != "cancelled",
                Registration.checked_in_at.isnot(None),
            )
            .scalar() or 0
        )

        # Calculate engagement rate as check-in rate (can be enhanced with real-time data)
        avg_engagement_rate = 0.0
        if total_registrations > 0:
            avg_engagement_rate = round((checked_in_count / total_registrations) * 100, 1)

        return {
            "totalAttendees": total_attendees,
            "totalAttendeesChange": None,  # TODO: Calculate historical comparison
            "activeSessions": active_sessions,
            "activeSessionsChange": None,
            "avgEngagementRate": avg_engagement_rate,
            "avgEngagementChange": None,
            "totalEvents": total_events,
            "totalEventsChange": None,
        }

    def get_checked_in_count_by_event(self, db: Session, *, event_id: str) -> int:
        """
        Gets the number of checked-in attendees for a specific event.
        """
        return (
            db.query(func.count(Registration.id))
            .filter(
                Registration.event_id == event_id,
                Registration.is_archived == "false",
                Registration.status != "cancelled",
                Registration.checked_in_at.isnot(None),
            )
            .scalar() or 0
        )


dashboard = CRUDDashboard()
