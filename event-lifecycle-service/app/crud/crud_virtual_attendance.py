# app/crud/crud_virtual_attendance.py
"""
CRUD operations for Virtual Attendance tracking.

Handles recording when attendees join/leave virtual sessions
and provides queries for attendance analytics.
"""
from typing import Optional, List
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import func, and_

from app.models.virtual_attendance import VirtualAttendance


class CRUDVirtualAttendance:
    """CRUD operations for virtual attendance tracking."""

    def join_session(
        self,
        db: Session,
        *,
        user_id: str,
        session_id: str,
        event_id: str,
        device_type: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> VirtualAttendance:
        """
        Record when a user joins a virtual session.

        If the user already has an active session (no left_at), we return that
        instead of creating a duplicate.
        """
        # Check for existing active attendance
        existing = self.get_active_attendance(db, user_id=user_id, session_id=session_id)
        if existing:
            return existing

        # Create new attendance record
        attendance = VirtualAttendance(
            user_id=user_id,
            session_id=session_id,
            event_id=event_id,
            joined_at=datetime.utcnow(),
            device_type=device_type,
            user_agent=user_agent,
        )
        db.add(attendance)
        db.commit()
        db.refresh(attendance)
        return attendance

    def leave_session(
        self,
        db: Session,
        *,
        user_id: str,
        session_id: str,
    ) -> Optional[VirtualAttendance]:
        """
        Record when a user leaves a virtual session.

        Updates the active attendance record with leave time and calculates duration.
        """
        attendance = self.get_active_attendance(db, user_id=user_id, session_id=session_id)
        if not attendance:
            return None

        now = datetime.utcnow()
        attendance.left_at = now
        attendance.watch_duration_seconds = int((now - attendance.joined_at).total_seconds())

        db.add(attendance)
        db.commit()
        db.refresh(attendance)
        return attendance

    def get_active_attendance(
        self,
        db: Session,
        *,
        user_id: str,
        session_id: str,
    ) -> Optional[VirtualAttendance]:
        """Get the user's currently active attendance for a session (not yet left)."""
        return (
            db.query(VirtualAttendance)
            .filter(
                and_(
                    VirtualAttendance.user_id == user_id,
                    VirtualAttendance.session_id == session_id,
                    VirtualAttendance.left_at.is_(None),
                )
            )
            .first()
        )

    def get_by_session(
        self,
        db: Session,
        *,
        session_id: str,
        include_active: bool = True,
    ) -> List[VirtualAttendance]:
        """Get all attendance records for a session."""
        query = db.query(VirtualAttendance).filter(
            VirtualAttendance.session_id == session_id
        )
        if not include_active:
            query = query.filter(VirtualAttendance.left_at.isnot(None))
        return query.order_by(VirtualAttendance.joined_at.desc()).all()

    def get_by_event(
        self,
        db: Session,
        *,
        event_id: str,
    ) -> List[VirtualAttendance]:
        """Get all attendance records for an event."""
        return (
            db.query(VirtualAttendance)
            .filter(VirtualAttendance.event_id == event_id)
            .order_by(VirtualAttendance.joined_at.desc())
            .all()
        )

    def get_active_viewers_count(
        self,
        db: Session,
        *,
        session_id: str,
    ) -> int:
        """Get the count of currently active viewers for a session."""
        return (
            db.query(func.count(VirtualAttendance.id))
            .filter(
                and_(
                    VirtualAttendance.session_id == session_id,
                    VirtualAttendance.left_at.is_(None),
                )
            )
            .scalar()
        ) or 0

    def get_active_viewers(
        self,
        db: Session,
        *,
        session_id: str,
    ) -> List[VirtualAttendance]:
        """Get all currently active viewers for a session."""
        return (
            db.query(VirtualAttendance)
            .filter(
                and_(
                    VirtualAttendance.session_id == session_id,
                    VirtualAttendance.left_at.is_(None),
                )
            )
            .order_by(VirtualAttendance.joined_at.asc())
            .all()
        )

    def get_session_stats(
        self,
        db: Session,
        *,
        session_id: str,
    ) -> dict:
        """
        Get aggregated statistics for a virtual session.

        Returns:
            - total_views: Total number of attendance records
            - unique_viewers: Count of unique users who attended
            - current_viewers: Currently watching
            - total_watch_time_seconds: Sum of all watch durations
            - avg_watch_time_seconds: Average watch duration
            - peak_viewers: Maximum concurrent viewers (approximate)
        """
        base_query = db.query(VirtualAttendance).filter(
            VirtualAttendance.session_id == session_id
        )

        # Total views
        total_views = base_query.count()

        # Unique viewers
        unique_viewers = (
            db.query(func.count(func.distinct(VirtualAttendance.user_id)))
            .filter(VirtualAttendance.session_id == session_id)
            .scalar()
        ) or 0

        # Current viewers
        current_viewers = self.get_active_viewers_count(db, session_id=session_id)

        # Total and average watch time (only for completed views)
        watch_time_stats = (
            db.query(
                func.sum(VirtualAttendance.watch_duration_seconds),
                func.avg(VirtualAttendance.watch_duration_seconds),
            )
            .filter(
                and_(
                    VirtualAttendance.session_id == session_id,
                    VirtualAttendance.watch_duration_seconds.isnot(None),
                )
            )
            .first()
        )

        total_watch_time = watch_time_stats[0] or 0
        avg_watch_time = int(watch_time_stats[1] or 0)

        return {
            "total_views": total_views,
            "unique_viewers": unique_viewers,
            "current_viewers": current_viewers,
            "total_watch_time_seconds": total_watch_time,
            "avg_watch_time_seconds": avg_watch_time,
            "avg_watch_duration_seconds": float(avg_watch_time),  # Alias for GraphQL
        }

    def get_event_stats(
        self,
        db: Session,
        *,
        event_id: str,
    ) -> dict:
        """
        Get aggregated virtual attendance statistics for an entire event.
        """
        base_query = db.query(VirtualAttendance).filter(
            VirtualAttendance.event_id == event_id
        )

        # Total views across all sessions
        total_views = base_query.count()

        # Unique viewers across all sessions
        unique_viewers = (
            db.query(func.count(func.distinct(VirtualAttendance.user_id)))
            .filter(VirtualAttendance.event_id == event_id)
            .scalar()
        ) or 0

        # Current viewers across all sessions
        current_viewers = (
            db.query(func.count(VirtualAttendance.id))
            .filter(
                and_(
                    VirtualAttendance.event_id == event_id,
                    VirtualAttendance.left_at.is_(None),
                )
            )
            .scalar()
        ) or 0

        # Total watch time
        total_watch_time = (
            db.query(func.sum(VirtualAttendance.watch_duration_seconds))
            .filter(
                and_(
                    VirtualAttendance.event_id == event_id,
                    VirtualAttendance.watch_duration_seconds.isnot(None),
                )
            )
            .scalar()
        ) or 0

        # Calculate average watch time
        avg_watch_time = (
            db.query(func.avg(VirtualAttendance.watch_duration_seconds))
            .filter(
                and_(
                    VirtualAttendance.event_id == event_id,
                    VirtualAttendance.watch_duration_seconds.isnot(None),
                )
            )
            .scalar()
        ) or 0

        return {
            "total_views": total_views,
            "unique_viewers": unique_viewers,
            "current_viewers": current_viewers,
            "total_watch_time_seconds": total_watch_time,
            "avg_watch_duration_seconds": float(avg_watch_time),
        }

    def get_user_event_attendance(
        self,
        db: Session,
        *,
        user_id: str,
        event_id: str,
    ) -> List[VirtualAttendance]:
        """
        Get all attendance records for a specific user at a specific event.
        Useful for showing a user's watch history.
        """
        return (
            db.query(VirtualAttendance)
            .filter(
                and_(
                    VirtualAttendance.user_id == user_id,
                    VirtualAttendance.event_id == event_id,
                )
            )
            .order_by(VirtualAttendance.joined_at.desc())
            .all()
        )


# Singleton instance
virtual_attendance = CRUDVirtualAttendance()
