# app/api/v1/endpoints/analytics.py
from typing import Optional, List
from datetime import date
from fastapi import APIRouter, Depends, HTTPException, status, Request, BackgroundTasks
from sqlalchemy.orm import Session
import logging

from app.api import deps
from app.db.session import get_db
from app.crud.crud_monetization_event import monetization_event
from app.schemas.analytics import (
    BatchTrackingDTO,
    TrackingResponse,
    MonetizationAnalyticsResponse,
    ConversionFunnelsResponse,
)
from app.schemas.token import TokenPayload
from app.utils.security import anonymize_ip

router = APIRouter(prefix="/analytics", tags=["Analytics"])
logger = logging.getLogger(__name__)


def _verify_analytics_access(db: Session, event_id: str, current_user: TokenPayload) -> None:
    """Verify the user is the event owner or belongs to the event's organization."""
    from app.models.event import Event

    event = db.query(Event).filter(Event.id == event_id).first()
    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Event not found"
        )

    # Allow if user belongs to the event's organization
    if hasattr(current_user, 'org_id') and current_user.org_id and event.organization_id == current_user.org_id:
        return

    # Allow if user is the event owner
    if hasattr(event, 'owner_id') and event.owner_id == current_user.sub:
        return

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Not authorized to view analytics for this event"
    )


# ==================== Event Tracking Endpoints ====================

@router.post("/track", response_model=TrackingResponse, status_code=status.HTTP_202_ACCEPTED)
async def track_events(
    batch: BatchTrackingDTO,
    background_tasks: BackgroundTasks,
    request: Request,
    event_id: str,  # Query parameter: which event/session
    session_token: Optional[str] = None,
    current_user: Optional[TokenPayload] = Depends(deps.get_current_user_optional),
    db: Session = Depends(get_db)
):
    """
    Bulk event tracking endpoint for monetization events.

    **Usage**:
    - Buffer events client-side
    - Send batch every 10 events or 30 seconds (whichever first)
    - Include session_token for anonymous tracking

    **Event Types**:
    - Offers: OFFER_VIEW, OFFER_CLICK, OFFER_ADD_TO_CART, OFFER_PURCHASE, OFFER_REFUND
    - Ads: AD_IMPRESSION, AD_VIEWABLE_IMPRESSION, AD_CLICK
    - Waitlist: WAITLIST_JOIN, WAITLIST_OFFER_SENT, etc.

    **Processing** (async via background task):
    1. Extract user_agent, IP from request
    2. Batch insert to monetization_events
    3. Update real-time counters in Redis (optional)

    **Response**: 202 Accepted (async processing)
    """
    user_agent = request.headers.get('user-agent')
    ip_address = request.client.host
    anonymized_ip = anonymize_ip(ip_address)

    # Queue for async processing
    background_tasks.add_task(
        _process_tracking_batch,
        events=batch.events,
        event_id=event_id,
        user_id=current_user.user_id if current_user else None,
        session_token=session_token,
        user_agent=user_agent,
        ip_address=anonymized_ip
    )

    return {
        "status": "accepted",
        "queued": len(batch.events)
    }


def _process_tracking_batch(
    events: List,
    event_id: str,
    user_id: Optional[str],
    session_token: Optional[str],
    user_agent: str,
    ip_address: str
):
    """
    Background task to process event tracking batch.
    Creates its own DB session to avoid using closed connections.
    """
    from app.db.session import SessionLocal

    db = SessionLocal()

    try:
        monetization_event.track_events_batch(
            db,
            events=events,
            event_id=event_id,
            user_id=user_id,
            session_token=session_token,
            user_agent=user_agent,
            ip_address=ip_address
        )
        logger.info(f"Successfully tracked {len(events)} monetization events for event {event_id}")
    except Exception as e:
        logger.error(f"Error processing tracking batch: {e}")
        db.rollback()
    finally:
        db.close()


# ==================== Analytics Endpoints ====================

@router.get("/events/{event_id}/monetization", response_model=MonetizationAnalyticsResponse)
async def get_monetization_analytics(
    event_id: str,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    db: Session = Depends(get_db),
    current_user: TokenPayload = Depends(deps.get_current_user),
):
    """
    Get comprehensive monetization analytics for an event.

    **Aggregates data from**:
    - Offers (views, clicks, purchases, revenue)
    - Ads (impressions, clicks, CTR)
    - Waitlist (joins, offers, acceptance rate)

    **Response includes**:
    - Revenue breakdown by day and source
    - Conversion funnels for offers
    - Top performing offers
    - Ad performance metrics
    - Waitlist engagement metrics
    - Unique users reached
    - Total interactions

    **Permissions**: Requires event organizer access
    """
    # Verify user has access to this event (must be event owner or org member)
    _verify_analytics_access(db, event_id, current_user)

    analytics = monetization_event.get_event_analytics(
        db,
        event_id=event_id,
        date_from=date_from,
        date_to=date_to
    )

    return {
        "event_id": event_id,
        "date_range": {
            "from": str(date_from) if date_from else None,
            "to": str(date_to) if date_to else None
        },
        **analytics
    }


@router.get("/events/{event_id}/conversion-funnels", response_model=ConversionFunnelsResponse)
async def get_conversion_funnels(
    event_id: str,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    db: Session = Depends(get_db),
    current_user: TokenPayload = Depends(deps.get_current_user),
):
    """
    Get conversion funnels for all offers in an event.

    **Funnel stages**:
    1. View → Click
    2. Click → Add to Cart
    3. Add to Cart → Purchase

    **Response includes**:
    - Per-offer funnel data
    - Conversion rates at each stage
    - Revenue per offer
    - Overall funnel summary

    **Data source**: Queries the `monetization_conversion_funnels` materialized view
    for fast performance.

    **Permissions**: Requires event organizer access
    """
    # Verify user has access to this event
    _verify_analytics_access(db, event_id, current_user)

    funnels = monetization_event.get_conversion_funnels(
        db,
        event_id=event_id,
        date_from=date_from,
        date_to=date_to
    )

    # Calculate summary
    total_views = sum(f['views'] for f in funnels)
    total_purchases = sum(f['purchases'] for f in funnels)
    total_revenue = sum(f['revenue_cents'] for f in funnels)
    avg_conversion = round((total_purchases / total_views * 100), 2) if total_views > 0 else 0

    summary = {
        "total_offers": len(funnels),
        "total_views": total_views,
        "total_purchases": total_purchases,
        "total_revenue_cents": total_revenue,
        "average_conversion_rate": avg_conversion
    }

    return {
        "event_id": event_id,
        "funnels": funnels,
        "summary": summary
    }


# ==================== Admin Endpoints ====================

@router.post("/admin/refresh-views", status_code=status.HTTP_202_ACCEPTED)
async def refresh_materialized_views(
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: TokenPayload = Depends(deps.get_current_user),
):
    """
    Manually trigger refresh of materialized views.

    **Refreshes**:
    - monetization_conversion_funnels
    - ad_analytics_daily (if needed)

    **Note**: This is typically done automatically via cron job every hour.
    This endpoint allows manual refresh if needed.

    **Permissions**: Requires admin access
    """
    # Check if user has admin access
    if not getattr(current_user, 'is_admin', False):
        raise HTTPException(status_code=403, detail="Admin access required")

    background_tasks.add_task(_refresh_views, db)

    return {
        "status": "accepted",
        "message": "Materialized views refresh queued"
    }


def _refresh_views(db: Session):
    """Background task to refresh materialized views"""
    try:
        monetization_event.refresh_materialized_views(db)
        logger.info("Successfully refreshed all materialized views")
    except Exception as e:
        logger.error(f"Error refreshing materialized views: {e}")
