# app/crud/crud_waitlist_analytics.py
import uuid
from typing import List, Optional, Dict
from sqlalchemy.orm import Session
from sqlalchemy import func, and_
from datetime import datetime, timedelta
from app.models.waitlist_analytics import WaitlistAnalytics


class CRUDWaitlistAnalytics:
    """CRUD operations for Waitlist Analytics caching and retrieval."""

    def upsert_metric(
        self,
        db: Session,
        event_id: str,
        metric_name: str,
        metric_value: float,
        session_id: Optional[str] = None
    ) -> WaitlistAnalytics:
        """
        Insert or update a cached metric.
        Uses unique constraint on (event_id, session_id, metric_name).
        """
        # Try to find existing metric
        existing = self.get_metric(db, event_id, metric_name, session_id)

        if existing:
            # Update existing metric
            existing.metric_value = metric_value
            existing.calculated_at = func.now()
            db.commit()
            db.refresh(existing)
            return existing
        else:
            # Create new metric
            metric = WaitlistAnalytics(
                id=f"wla_{uuid.uuid4().hex[:12]}",
                event_id=event_id,
                session_id=session_id,
                metric_name=metric_name,
                metric_value=metric_value
            )
            db.add(metric)
            db.commit()
            db.refresh(metric)
            return metric

    def get_metric(
        self,
        db: Session,
        event_id: str,
        metric_name: str,
        session_id: Optional[str] = None
    ) -> Optional[WaitlistAnalytics]:
        """Get a specific cached metric."""
        query = db.query(WaitlistAnalytics).filter(
            and_(
                WaitlistAnalytics.event_id == event_id,
                WaitlistAnalytics.metric_name == metric_name
            )
        )

        if session_id:
            query = query.filter(WaitlistAnalytics.session_id == session_id)
        else:
            query = query.filter(WaitlistAnalytics.session_id.is_(None))

        return query.first()

    def get_event_metrics(self, db: Session, event_id: str) -> Dict[str, float]:
        """
        Get all event-level metrics (where session_id is NULL).
        Returns a dictionary of metric_name -> metric_value.
        """
        metrics = db.query(WaitlistAnalytics).filter(
            and_(
                WaitlistAnalytics.event_id == event_id,
                WaitlistAnalytics.session_id.is_(None)
            )
        ).all()

        return {metric.metric_name: float(metric.metric_value) for metric in metrics}

    def get_session_metrics(self, db: Session, session_id: str) -> Dict[str, float]:
        """
        Get all session-level metrics.
        Returns a dictionary of metric_name -> metric_value.
        """
        metrics = db.query(WaitlistAnalytics).filter(
            WaitlistAnalytics.session_id == session_id
        ).all()

        return {metric.metric_name: float(metric.metric_value) for metric in metrics}

    def get_all_session_metrics_for_event(
        self,
        db: Session,
        event_id: str
    ) -> Dict[str, Dict[str, float]]:
        """
        Get metrics for all sessions in an event.
        Returns: {session_id: {metric_name: metric_value}}
        """
        metrics = db.query(WaitlistAnalytics).filter(
            and_(
                WaitlistAnalytics.event_id == event_id,
                WaitlistAnalytics.session_id.isnot(None)
            )
        ).all()

        result = {}
        for metric in metrics:
            if metric.session_id not in result:
                result[metric.session_id] = {}
            result[metric.session_id][metric.metric_name] = float(metric.metric_value)

        return result

    def delete_old_metrics(
        self,
        db: Session,
        older_than_days: int = 7
    ) -> int:
        """
        Delete cached metrics older than specified days.
        Returns number of deleted records.
        """
        cutoff_date = datetime.utcnow() - timedelta(days=older_than_days)
        deleted = db.query(WaitlistAnalytics).filter(
            WaitlistAnalytics.calculated_at < cutoff_date
        ).delete()
        db.commit()
        return deleted

    def delete_event_metrics(self, db: Session, event_id: str) -> int:
        """
        Delete all metrics for a specific event.
        Returns number of deleted records.
        """
        deleted = db.query(WaitlistAnalytics).filter(
            WaitlistAnalytics.event_id == event_id
        ).delete()
        db.commit()
        return deleted

    def delete_session_metrics(self, db: Session, session_id: str) -> int:
        """
        Delete all metrics for a specific session.
        Returns number of deleted records.
        """
        deleted = db.query(WaitlistAnalytics).filter(
            WaitlistAnalytics.session_id == session_id
        ).delete()
        db.commit()
        return deleted

    def refresh_event_analytics(
        self,
        db: Session,
        event_id: str,
        metrics: Dict[str, float]
    ) -> None:
        """
        Bulk refresh all event-level metrics.
        Deletes old metrics and inserts new ones.
        """
        # Delete old event-level metrics
        db.query(WaitlistAnalytics).filter(
            and_(
                WaitlistAnalytics.event_id == event_id,
                WaitlistAnalytics.session_id.is_(None)
            )
        ).delete()

        # Insert new metrics
        for metric_name, metric_value in metrics.items():
            self.upsert_metric(db, event_id, metric_name, metric_value)


# Singleton instance
waitlist_analytics_crud = CRUDWaitlistAnalytics()
