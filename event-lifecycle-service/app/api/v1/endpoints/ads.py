# app/api/v1/endpoints/ads.py
from typing import List, Optional
from datetime import date
from fastapi import APIRouter, Depends, HTTPException, status, Request, BackgroundTasks, Header
from sqlalchemy.orm import Session
from redis import Redis

from app.api import deps
from app.db.session import get_db
from app.crud import crud_ad
from app.crud.crud_ad_event import ad_event
from app.schemas.ad import (
    Ad, AdCreate, AdUpdate,
    AdCreateDTO, AdUpdateDTO, AdResponse,
    BatchImpressionDTO, ClickTrackingResponse,
    AdAnalyticsResponse, EventAdAnalyticsResponse
)
from app.schemas.token import TokenPayload

router = APIRouter(tags=["Ads"])


# ==================== Ad Management Endpoints ====================

@router.post(
    "/organizations/{orgId}/ads",
    response_model=AdResponse,
    status_code=status.HTTP_201_CREATED
)
def create_ad(
    orgId: str,
    ad_in: AdCreateDTO,
    db: Session = Depends(get_db),
    current_user: TokenPayload = Depends(deps.get_current_user),
):
    """
    Create a new advertisement for an organization.

    **Validations**:
    - media_url must be valid URL
    - click_url must be valid URL
    - content_type must be BANNER|VIDEO|SPONSORED_SESSION|INTERSTITIAL
    - placements must be valid (EVENT_HERO, SESSION_LIST, SIDEBAR, etc.)
    """
    if current_user.org_id != orgId:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized"
        )

    ad = crud_ad.ad.create_ad(db, ad_data=ad_in, organization_id=orgId)
    return ad


@router.get("/organizations/{orgId}/ads", response_model=List[AdResponse])
def list_ads(
    orgId: str,
    active_only: bool = False,
    db: Session = Depends(get_db),
    current_user: TokenPayload = Depends(deps.get_current_user),
):
    """
    List all ads for an organization.
    """
    if current_user.org_id != orgId:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized"
        )
    return crud_ad.ad.get_multi_by_organization(db, org_id=orgId)


@router.get("/events/{event_id}/ads", response_model=List[AdResponse])
def get_event_ads(
    event_id: str,
    active_only: bool = False,
    db: Session = Depends(get_db),
    current_user: TokenPayload = Depends(deps.get_current_user),
):
    """
    Get all ads for an event.
    """
    ads = crud_ad.ad.get_multi_by_event(db, event_id=event_id, active_only=active_only)
    return ads


@router.patch("/{ad_id}", response_model=AdResponse)
def update_ad(
    ad_id: str,
    ad_update: AdUpdateDTO,
    db: Session = Depends(get_db),
    current_user: TokenPayload = Depends(deps.get_current_user),
):
    """
    Update an existing ad.
    """
    ad = crud_ad.ad.get(db, id=ad_id)
    if not ad:
        raise HTTPException(status_code=404, detail="Ad not found")

    if ad.organization_id != current_user.org_id:
        raise HTTPException(status_code=403, detail="Not authorized")

    updated_ad = crud_ad.ad.update_ad(db, ad_id=ad_id, ad_data=ad_update)
    return updated_ad


@router.delete("/{ad_id}", status_code=status.HTTP_204_NO_CONTENT)
def archive_ad(
    ad_id: str,
    db: Session = Depends(get_db),
    current_user: TokenPayload = Depends(deps.get_current_user),
):
    """
    Soft delete (archive) an ad.
    Set is_archived = true, is_active = false
    """
    ad = crud_ad.ad.get(db, id=ad_id)
    if not ad:
        raise HTTPException(status_code=404, detail="Ad not found")

    if ad.organization_id != current_user.org_id:
        raise HTTPException(status_code=403, detail="Not authorized")

    crud_ad.ad.archive(db, id=ad_id)
    return None


# ==================== Ad Serving Endpoint ====================

@router.get("/serve", response_model=List[AdResponse])
def serve_ads(
    event_id: str,
    placement: str,
    session_id: Optional[str] = None,
    limit: int = 3,
    session_token: Optional[str] = Header(None, alias="X-Session-Token"),
    db: Session = Depends(get_db),
    redis_client: Redis = Depends(deps.get_redis),
    current_user: Optional[TokenPayload] = Depends(deps.get_current_user_optional),
):
    """
    Serve ads to attendee based on context and frequency capping.

    **Ad Selection Algorithm**:
    1. Filter by: is_active=true, NOW() BETWEEN starts_at AND ends_at, placement match
    2. Filter by targeting: session_id if specified
    3. Apply frequency capping: check Redis for user/session impression count
    4. Weighted random selection: ads with higher weight more likely
    5. Return up to {limit} ads

    **Frequency Capping (Redis)**:
    - Key: ad_frequency:{session_token}:{ad_id}
    - Value: impression count
    - TTL: 1 hour (3600 seconds)
    - If count >= frequency_cap, exclude ad from selection
    """
    # Get active ads
    ads = crud_ad.ad.get_active_ads(
        db, event_id=event_id, placement=placement, session_id=session_id
    )

    if not ads:
        return []

    # Apply frequency capping if session_token provided
    if session_token:
        filtered_ads = []
        for ad in ads:
            key = f"ad_frequency:{session_token}:{ad.id}"
            try:
                count = redis_client.get(key)
                impression_count = int(count) if count else 0

                if impression_count < ad.frequency_cap:
                    filtered_ads.append(ad)
            except Exception:
                # If Redis fails, include the ad (fail open)
                filtered_ads.append(ad)

        ads = filtered_ads

    # Weighted random selection
    selected_ads = crud_ad.ad.select_ads_weighted_random(ads, limit=limit)

    return selected_ads


# ==================== Ad Tracking Endpoints ====================

@router.post("/track/impressions", status_code=status.HTTP_202_ACCEPTED)
def track_impressions(
    batch: BatchImpressionDTO,
    request: Request,
    background_tasks: BackgroundTasks,
    session_token: str = Header(..., alias="X-Session-Token"),
    db: Session = Depends(get_db),
    redis_client: Redis = Depends(deps.get_redis),
    current_user: Optional[TokenPayload] = Depends(deps.get_current_user_optional),
):
    """
    Bulk track ad impressions (async processing).

    **Processing**:
    1. Validate all ad_ids exist
    2. Filter viewable impressions (viewport >= 50% AND duration >= 1000ms)
    3. Batch insert to ad_events table
    4. Update Redis frequency counters
    5. Queue for real-time analytics update (optional)

    **Viewability Standard** (IAB):
    - Display ads: 50% of pixels visible for 1+ second
    - Video ads: 50% of pixels visible for 2+ seconds

    **Response**: 202 Accepted (async processing)
    """
    user_agent = request.headers.get('user-agent')
    ip_address = request.client.host

    # Process in background
    background_tasks.add_task(
        _process_impressions,
        batch=batch,
        user_id=current_user.user_id if current_user else None,
        session_token=session_token,
        user_agent=user_agent,
        ip_address=ip_address,
        db=db,
        redis_client=redis_client
    )

    return {"status": "accepted", "queued": len(batch.impressions)}


def _process_impressions(
    batch: BatchImpressionDTO,
    user_id: Optional[str],
    session_token: str,
    user_agent: str,
    ip_address: str,
    db: Session,
    redis_client: Redis
):
    """Background task to process impression tracking."""
    # Track impressions in database
    ad_event.track_impressions_batch(
        db,
        impressions=batch.impressions,
        user_id=user_id,
        session_token=session_token,
        user_agent=user_agent,
        ip_address=ip_address
    )

    # Update Redis frequency counters
    for imp in batch.impressions:
        # Only count viewable impressions for frequency capping
        if imp.viewport_percentage >= 50 and imp.viewable_duration_ms >= 1000:
            key = f"ad_frequency:{session_token}:{imp.ad_id}"
            try:
                redis_client.incr(key)
                redis_client.expire(key, 3600)  # 1 hour TTL
            except Exception:
                # Fail silently if Redis is unavailable
                pass


@router.post("/track/click/{ad_id}", response_model=ClickTrackingResponse)
def track_click(
    ad_id: str,
    request: Request,
    context: Optional[str] = None,
    session_token: str = Header(..., alias="X-Session-Token"),
    db: Session = Depends(get_db),
    current_user: Optional[TokenPayload] = Depends(deps.get_current_user_optional),
):
    """
    Track ad click and return click_url for redirect.

    **Processing**:
    1. Insert click event to ad_events
    2. Return ad's click_url for client-side redirect

    **Response**:
    {
      "redirect_url": "https://sponsor-site.com/promo",
      "open_in_new_tab": true
    }
    """
    # Get the ad
    ad = crud_ad.ad.get(db, id=ad_id)
    if not ad:
        raise HTTPException(status_code=404, detail="Ad not found")

    # Track the click
    user_agent = request.headers.get('user-agent')
    ip_address = request.client.host
    referer = request.headers.get('referer')

    ad_event.track_click(
        db,
        ad_id=ad_id,
        user_id=current_user.user_id if current_user else None,
        session_token=session_token,
        context=context,
        user_agent=user_agent,
        ip_address=ip_address,
        referer=referer
    )

    return {
        "redirect_url": ad.click_url,
        "open_in_new_tab": True
    }


# ==================== Analytics Endpoints ====================

@router.get("/{ad_id}/analytics", response_model=AdAnalyticsResponse)
def get_ad_analytics(
    ad_id: str,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    db: Session = Depends(get_db),
    current_user: TokenPayload = Depends(deps.get_current_user),
):
    """
    Get analytics for a specific ad.

    **Metrics**:
    - Total impressions
    - Viewable impressions (IAB standard)
    - Total clicks
    - CTR (click-through rate)
    - Unique users reached
    - Breakdown by day
    """
    # Get the ad
    ad = crud_ad.ad.get(db, id=ad_id)
    if not ad:
        raise HTTPException(status_code=404, detail="Ad not found")

    if ad.organization_id != current_user.org_id:
        raise HTTPException(status_code=403, detail="Not authorized")

    # Get analytics
    analytics = ad_event.get_ad_analytics(
        db, ad_id=ad_id, date_from=date_from, date_to=date_to
    )

    return {
        "ad_id": ad_id,
        "ad_name": ad.name,
        **analytics
    }


@router.get("/events/{event_id}/analytics", response_model=EventAdAnalyticsResponse)
def get_event_ad_analytics(
    event_id: str,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    db: Session = Depends(get_db),
    current_user: TokenPayload = Depends(deps.get_current_user),
):
    """
    Aggregate analytics for all ads in an event.

    **Response**:
    {
      "total_impressions": 15420,
      "total_clicks": 234,
      "average_ctr": 1.52,
      "top_performers": [
        {"ad_id": "...", "name": "Sponsor X", "impressions": 5000, "ctr": 2.1},
        ...
      ],
      "by_placement": {
        "EVENT_HERO": {"impressions": 8000, "clicks": 150},
        "SIDEBAR": {"impressions": 7420, "clicks": 84}
      }
    }
    """
    analytics = ad_event.get_event_ad_analytics(
        db, event_id=event_id, date_from=date_from, date_to=date_to
    )

    return analytics
