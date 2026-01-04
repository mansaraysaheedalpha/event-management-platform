# app/utils/waitlist_analytics.py
"""
Waitlist Analytics Calculations

This module provides functions to calculate comprehensive analytics for
waitlist management, including acceptance rates, wait times, and conversion metrics.
"""

from typing import Dict, List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, extract, case
from datetime import datetime, timedelta
import logging

from app.models.session_waitlist import SessionWaitlist, WaitlistEvent
from app.models.session import Session as SessionModel
from app.crud.crud_waitlist_analytics import waitlist_analytics_crud

logger = logging.getLogger(__name__)


def calculate_event_waitlist_analytics(db: Session, event_id: str) -> Dict[str, float]:
    """
    Calculate comprehensive waitlist analytics for an entire event.

    Metrics calculated:
    - total_waitlist_entries: Total number of waitlist entries
    - active_waitlist_count: Users currently waiting
    - total_offers_issued: Total offers sent
    - total_offers_accepted: Offers accepted
    - total_offers_declined: Offers declined
    - total_offers_expired: Offers that expired
    - acceptance_rate: Percentage of offers accepted
    - decline_rate: Percentage of offers declined
    - expiry_rate: Percentage of offers expired
    - average_wait_time_minutes: Average time from join to offer
    - conversion_rate: Percentage of waiting users who got accepted

    Args:
        db: Database session
        event_id: Event ID

    Returns:
        Dictionary of metric_name -> metric_value
    """
    # Get all sessions for this event
    sessions = db.query(SessionModel.id).filter(SessionModel.event_id == event_id).all()
    session_ids = [s.id for s in sessions]

    if not session_ids:
        logger.warning(f"No sessions found for event {event_id}")
        return {}

    # Total waitlist entries across all sessions
    total_entries = db.query(func.count(SessionWaitlist.id)).filter(
        SessionWaitlist.session_id.in_(session_ids)
    ).scalar() or 0

    # Active waitlist count (WAITING status)
    active_count = db.query(func.count(SessionWaitlist.id)).filter(
        and_(
            SessionWaitlist.session_id.in_(session_ids),
            SessionWaitlist.status == 'WAITING'
        )
    ).scalar() or 0

    # Count by status
    status_counts = db.query(
        SessionWaitlist.status,
        func.count(SessionWaitlist.id)
    ).filter(
        SessionWaitlist.session_id.in_(session_ids)
    ).group_by(SessionWaitlist.status).all()

    status_dict = {status: count for status, count in status_counts}

    total_offered = status_dict.get('OFFERED', 0)
    total_accepted = status_dict.get('ACCEPTED', 0)
    total_declined = status_dict.get('DECLINED', 0)
    total_expired = status_dict.get('EXPIRED', 0)

    # Calculate total offers issued (anyone who moved beyond WAITING)
    total_offers_issued = total_offered + total_accepted + total_declined + total_expired

    # Calculate rates
    acceptance_rate = (total_accepted / total_offers_issued * 100) if total_offers_issued > 0 else 0
    decline_rate = (total_declined / total_offers_issued * 100) if total_offers_issued > 0 else 0
    expiry_rate = (total_expired / total_offers_issued * 100) if total_offers_issued > 0 else 0
    conversion_rate = (total_accepted / total_entries * 100) if total_entries > 0 else 0

    # Calculate average wait time (time from joined to offer sent)
    avg_wait_time = db.query(
        func.avg(
            extract('epoch', SessionWaitlist.offer_sent_at - SessionWaitlist.joined_at) / 60
        )
    ).filter(
        and_(
            SessionWaitlist.session_id.in_(session_ids),
            SessionWaitlist.offer_sent_at.isnot(None)
        )
    ).scalar() or 0

    metrics = {
        'total_waitlist_entries': float(total_entries),
        'active_waitlist_count': float(active_count),
        'total_offers_issued': float(total_offers_issued),
        'total_offers_accepted': float(total_accepted),
        'total_offers_declined': float(total_declined),
        'total_offers_expired': float(total_expired),
        'acceptance_rate': round(acceptance_rate, 2),
        'decline_rate': round(decline_rate, 2),
        'expiry_rate': round(expiry_rate, 2),
        'conversion_rate': round(conversion_rate, 2),
        'average_wait_time_minutes': round(avg_wait_time, 2)
    }

    logger.info(f"Calculated event analytics for {event_id}: {metrics}")
    return metrics


def calculate_session_waitlist_analytics(db: Session, session_id: str) -> Dict[str, float]:
    """
    Calculate comprehensive waitlist analytics for a single session.

    Args:
        db: Database session
        session_id: Session ID

    Returns:
        Dictionary of metric_name -> metric_value
    """
    # Total waitlist entries
    total_entries = db.query(func.count(SessionWaitlist.id)).filter(
        SessionWaitlist.session_id == session_id
    ).scalar() or 0

    # Active waitlist count
    active_count = db.query(func.count(SessionWaitlist.id)).filter(
        and_(
            SessionWaitlist.session_id == session_id,
            SessionWaitlist.status == 'WAITING'
        )
    ).scalar() or 0

    # Count by status
    status_counts = db.query(
        SessionWaitlist.status,
        func.count(SessionWaitlist.id)
    ).filter(
        SessionWaitlist.session_id == session_id
    ).group_by(SessionWaitlist.status).all()

    status_dict = {status: count for status, count in status_counts}

    total_offered = status_dict.get('OFFERED', 0)
    total_accepted = status_dict.get('ACCEPTED', 0)
    total_declined = status_dict.get('DECLINED', 0)
    total_expired = status_dict.get('EXPIRED', 0)

    total_offers_issued = total_offered + total_accepted + total_declined + total_expired

    # Calculate rates
    acceptance_rate = (total_accepted / total_offers_issued * 100) if total_offers_issued > 0 else 0
    decline_rate = (total_declined / total_offers_issued * 100) if total_offers_issued > 0 else 0
    expiry_rate = (total_expired / total_offers_issued * 100) if total_offers_issued > 0 else 0
    conversion_rate = (total_accepted / total_entries * 100) if total_entries > 0 else 0

    # Average wait time
    avg_wait_time = db.query(
        func.avg(
            extract('epoch', SessionWaitlist.offer_sent_at - SessionWaitlist.joined_at) / 60
        )
    ).filter(
        and_(
            SessionWaitlist.session_id == session_id,
            SessionWaitlist.offer_sent_at.isnot(None)
        )
    ).scalar() or 0

    # Average response time (time from offer sent to responded)
    avg_response_time = db.query(
        func.avg(
            extract('epoch', SessionWaitlist.offer_responded_at - SessionWaitlist.offer_sent_at) / 60
        )
    ).filter(
        and_(
            SessionWaitlist.session_id == session_id,
            SessionWaitlist.offer_responded_at.isnot(None)
        )
    ).scalar() or 0

    # Count by priority tier
    priority_counts = db.query(
        SessionWaitlist.priority_tier,
        func.count(SessionWaitlist.id)
    ).filter(
        SessionWaitlist.session_id == session_id
    ).group_by(SessionWaitlist.priority_tier).all()

    priority_dict = {tier: count for tier, count in priority_counts}

    metrics = {
        'total_waitlist_entries': float(total_entries),
        'active_waitlist_count': float(active_count),
        'total_offers_issued': float(total_offers_issued),
        'total_offers_accepted': float(total_accepted),
        'total_offers_declined': float(total_declined),
        'total_offers_expired': float(total_expired),
        'acceptance_rate': round(acceptance_rate, 2),
        'decline_rate': round(decline_rate, 2),
        'expiry_rate': round(expiry_rate, 2),
        'conversion_rate': round(conversion_rate, 2),
        'average_wait_time_minutes': round(avg_wait_time, 2),
        'average_response_time_minutes': round(avg_response_time, 2),
        'vip_entries': float(priority_dict.get('VIP', 0)),
        'premium_entries': float(priority_dict.get('PREMIUM', 0)),
        'standard_entries': float(priority_dict.get('STANDARD', 0))
    }

    logger.info(f"Calculated session analytics for {session_id}: {metrics}")
    return metrics


def refresh_event_analytics_cache(db: Session, event_id: str) -> None:
    """
    Calculate and cache event-level analytics in the database.

    This function should be called periodically (e.g., every 5-10 minutes)
    to refresh cached analytics for dashboard displays.

    Args:
        db: Database session
        event_id: Event ID
    """
    try:
        # Calculate event-level metrics
        event_metrics = calculate_event_waitlist_analytics(db, event_id)

        # Upsert each metric
        for metric_name, metric_value in event_metrics.items():
            waitlist_analytics_crud.upsert_metric(
                db=db,
                event_id=event_id,
                metric_name=metric_name,
                metric_value=metric_value,
                session_id=None  # Event-level, no session
            )

        logger.info(f"Refreshed analytics cache for event {event_id}")

    except Exception as e:
        logger.error(f"Failed to refresh analytics cache for event {event_id}: {e}", exc_info=True)


def refresh_session_analytics_cache(db: Session, session_id: str, event_id: str) -> None:
    """
    Calculate and cache session-level analytics in the database.

    Args:
        db: Database session
        session_id: Session ID
        event_id: Event ID (for foreign key)
    """
    try:
        # Calculate session-level metrics
        session_metrics = calculate_session_waitlist_analytics(db, session_id)

        # Upsert each metric
        for metric_name, metric_value in session_metrics.items():
            waitlist_analytics_crud.upsert_metric(
                db=db,
                event_id=event_id,
                metric_name=metric_name,
                metric_value=metric_value,
                session_id=session_id
            )

        logger.info(f"Refreshed analytics cache for session {session_id}")

    except Exception as e:
        logger.error(f"Failed to refresh analytics cache for session {session_id}: {e}", exc_info=True)


def get_cached_event_analytics(db: Session, event_id: str, max_age_minutes: int = 10) -> Optional[Dict[str, float]]:
    """
    Get cached event analytics if available and recent enough.

    Args:
        db: Database session
        event_id: Event ID
        max_age_minutes: Maximum age of cached data in minutes

    Returns:
        Dictionary of cached metrics or None if cache is stale/empty
    """
    metrics = waitlist_analytics_crud.get_event_metrics(db, event_id)

    if not metrics:
        return None

    # Check if cache is recent (check the first metric's calculated_at timestamp)
    first_metric = waitlist_analytics_crud.get_metric(db, event_id, list(metrics.keys())[0])
    if first_metric:
        age = datetime.utcnow() - first_metric.calculated_at
        if age.total_seconds() / 60 > max_age_minutes:
            logger.info(f"Analytics cache for event {event_id} is stale ({age.total_seconds() / 60:.1f} min old)")
            return None

    return metrics


def get_event_analytics(db: Session, event_id: str, use_cache: bool = True) -> Dict[str, float]:
    """
    Get event analytics, using cache if available or calculating fresh.

    Args:
        db: Database session
        event_id: Event ID
        use_cache: Whether to try using cached data

    Returns:
        Dictionary of analytics metrics
    """
    if use_cache:
        cached = get_cached_event_analytics(db, event_id)
        if cached:
            logger.info(f"Using cached analytics for event {event_id}")
            return cached

    # Calculate fresh
    logger.info(f"Calculating fresh analytics for event {event_id}")
    metrics = calculate_event_waitlist_analytics(db, event_id)

    # Cache the results
    refresh_event_analytics_cache(db, event_id)

    return metrics
