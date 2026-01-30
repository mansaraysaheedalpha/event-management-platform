# app/api/v1/endpoints/sponsor_campaigns.py
"""
API endpoints for sponsor email campaigns.

Production features:
- Create and send campaigns to filtered lead audiences
- Async processing via Kafka
- Campaign analytics and tracking
- Open/click tracking
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks, Request
from sqlalchemy.orm import Session
import logging

from app.api import deps
from app.db.session import get_db
from app.core.limiter import limiter
from app.core.kafka_producer import get_kafka_producer
from app.crud.crud_sponsor import sponsor_user, sponsor
from app.crud.crud_sponsor_campaign import sponsor_campaign
from app.crud.crud_campaign_delivery import campaign_delivery
from app.crud.crud_event import event
from app.schemas.sponsor_campaign import (
    CampaignCreate,
    CampaignUpdate,
    CampaignResponse,
    CampaignListResponse,
    DeliveryResponse,
    CampaignStats,
)
from app.schemas.token import TokenPayload
from app.services.ai_message_generator import ai_generator
from kafka import KafkaProducer
import json
from datetime import datetime
from pydantic import BaseModel

logger = logging.getLogger(__name__)
router = APIRouter()

# Kafka topic for campaign processing
KAFKA_TOPIC = "sponsor.campaigns.v1"


@router.post("/sponsors/{sponsor_id}/campaigns", response_model=CampaignResponse)
@limiter.limit("10/minute")
async def create_campaign(
    request: Request,
    sponsor_id: str,
    campaign_in: CampaignCreate,
    db: Session = Depends(get_db),
    current_user: TokenPayload = Depends(deps.get_current_user),
    kafka_producer: Optional[KafkaProducer] = Depends(get_kafka_producer),
):
    """
    Create a new email campaign for a sponsor.

    The campaign is created in 'draft' status and can be sent immediately
    or scheduled for later. The actual sending is processed asynchronously via Kafka.

    Permissions:
    - User must be an active sponsor representative with can_send_messages permission
    - Sponsor must have messaging enabled in their tier
    """
    # Verify user is sponsor representative
    su = sponsor_user.get_by_user_and_sponsor(
        db, user_id=current_user.sub, sponsor_id=sponsor_id
    )
    if not su or not su.is_active or not su.can_message_attendees:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to send messages for this sponsor"
        )

    # Verify sponsor has messaging enabled
    sponsor_obj = sponsor.get(db, id=sponsor_id)
    if not sponsor_obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Sponsor not found"
        )

    # Check if sponsor tier allows messaging
    if sponsor_obj.tier and not sponsor_obj.tier.can_send_messages:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your sponsor tier does not include messaging. Please upgrade."
        )

    # Get recipient count before creating campaign
    recipients = sponsor_campaign.get_recipients(
        db,
        sponsor_id=sponsor_id,
        audience_type=campaign_in.audience_type,
        audience_filter=campaign_in.audience_filter,
    )

    if len(recipients) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"No recipients found for audience type '{campaign_in.audience_type}'"
        )

    # Create campaign
    campaign = sponsor_campaign.create(
        db,
        sponsor_id=sponsor_id,
        event_id=sponsor_obj.event_id,
        created_by_user_id=current_user.sub,
        created_by_user_name=getattr(current_user, 'full_name', None) or current_user.email,
        obj_in=campaign_in,
    )

    # If not scheduled, queue for immediate sending
    if not campaign_in.scheduled_at:
        # Mark as queued
        sponsor_campaign.mark_queued(db, campaign=campaign, recipient_count=len(recipients))

        # Publish to Kafka for async processing
        if kafka_producer:
            try:
                event = {
                    "event_type": "campaign.send",
                    "campaign_id": campaign.id,
                    "sponsor_id": sponsor_id,
                    "event_id": sponsor_obj.event_id,
                    "recipient_count": len(recipients),
                    "created_at": datetime.utcnow().isoformat(),
                }
                # Send message and wait for delivery confirmation
                future = kafka_producer.send(
                    KAFKA_TOPIC,
                    key=campaign.id.encode('utf-8'),
                    value=event
                )
                # Wait for the message to be delivered (blocks until sent or error)
                # Timeout after 10 seconds to avoid hanging
                record_metadata = future.get(timeout=10)
                logger.info(
                    f"Campaign {campaign.id} queued to Kafka successfully. "
                    f"Topic: {record_metadata.topic}, Partition: {record_metadata.partition}, "
                    f"Offset: {record_metadata.offset}"
                )
            except Exception as e:
                logger.error(f"Failed to queue campaign to Kafka: {e}", exc_info=True)
                sponsor_campaign.mark_failed(db, campaign=campaign, error=str(e))
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Failed to queue campaign for sending. Please try again."
                )
        else:
            logger.warning("Kafka producer not available. Campaign queued but not sent.")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Messaging service temporarily unavailable"
            )

    return campaign


@router.get("/sponsors/{sponsor_id}/campaigns", response_model=CampaignListResponse)
@limiter.limit("30/minute")
async def list_campaigns(
    request: Request,
    sponsor_id: str,
    skip: int = 0,
    limit: int = 20,
    status: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: TokenPayload = Depends(deps.get_current_user),
):
    """
    Get all campaigns for a sponsor with optional status filtering.

    Permissions:
    - User must be an active sponsor representative
    """
    # Verify user is sponsor representative
    su = sponsor_user.get_by_user_and_sponsor(
        db, user_id=current_user.sub, sponsor_id=sponsor_id
    )
    if not su or not su.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to view campaigns for this sponsor"
        )

    # Get campaigns
    campaigns = sponsor_campaign.get_by_sponsor(
        db,
        sponsor_id=sponsor_id,
        skip=skip,
        limit=limit,
        status=status,
    )

    total = sponsor_campaign.count_by_sponsor(db, sponsor_id=sponsor_id, status=status)

    return CampaignListResponse(
        campaigns=campaigns,
        total=total,
        page=skip // limit + 1,
        page_size=limit,
    )


@router.get("/sponsors/{sponsor_id}/campaigns/{campaign_id}", response_model=CampaignResponse)
@limiter.limit("60/minute")
async def get_campaign(
    request: Request,
    sponsor_id: str,
    campaign_id: str,
    db: Session = Depends(get_db),
    current_user: TokenPayload = Depends(deps.get_current_user),
):
    """
    Get campaign details by ID.

    Permissions:
    - User must be an active sponsor representative
    """
    # Verify user is sponsor representative
    su = sponsor_user.get_by_user_and_sponsor(
        db, user_id=current_user.sub, sponsor_id=sponsor_id
    )
    if not su or not su.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized"
        )

    campaign = sponsor_campaign.get(db, campaign_id=campaign_id)
    if not campaign or campaign.sponsor_id != sponsor_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Campaign not found"
        )

    return campaign


@router.get("/sponsors/{sponsor_id}/campaigns/{campaign_id}/stats", response_model=CampaignStats)
@limiter.limit("30/minute")
async def get_campaign_stats(
    request: Request,
    sponsor_id: str,
    campaign_id: str,
    db: Session = Depends(get_db),
    current_user: TokenPayload = Depends(deps.get_current_user),
):
    """
    Get detailed analytics for a campaign.

    Includes:
    - Delivery rates
    - Open rates
    - Click rates
    - Bounce rates
    - Status breakdown
    """
    # Verify user is sponsor representative
    su = sponsor_user.get_by_user_and_sponsor(
        db, user_id=current_user.sub, sponsor_id=sponsor_id
    )
    if not su or not su.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized"
        )

    campaign = sponsor_campaign.get(db, campaign_id=campaign_id)
    if not campaign or campaign.sponsor_id != sponsor_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Campaign not found"
        )

    # Get stats
    stats = sponsor_campaign.get_stats(db, campaign_id=campaign_id)
    return CampaignStats(**stats)


@router.get("/sponsors/{sponsor_id}/campaigns/{campaign_id}/deliveries", response_model=List[DeliveryResponse])
@limiter.limit("30/minute")
async def get_campaign_deliveries(
    request: Request,
    sponsor_id: str,
    campaign_id: str,
    skip: int = 0,
    limit: int = 50,
    status: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: TokenPayload = Depends(deps.get_current_user),
):
    """
    Get delivery status for each recipient in a campaign.

    Useful for:
    - Debugging failed deliveries
    - Identifying bounced emails
    - Viewing per-lead engagement
    """
    # Verify user is sponsor representative
    su = sponsor_user.get_by_user_and_sponsor(
        db, user_id=current_user.sub, sponsor_id=sponsor_id
    )
    if not su or not su.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized"
        )

    campaign = sponsor_campaign.get(db, campaign_id=campaign_id)
    if not campaign or campaign.sponsor_id != sponsor_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Campaign not found"
        )

    # Get deliveries
    deliveries = campaign_delivery.get_by_campaign(
        db,
        campaign_id=campaign_id,
        skip=skip,
        limit=limit,
        status=status,
    )

    return deliveries


@router.delete("/sponsors/{sponsor_id}/campaigns/{campaign_id}")
@limiter.limit("10/minute")
async def delete_campaign(
    request: Request,
    sponsor_id: str,
    campaign_id: str,
    db: Session = Depends(get_db),
    current_user: TokenPayload = Depends(deps.get_current_user),
):
    """
    Delete a campaign (only allowed if status is 'draft').

    Once a campaign is queued or sent, it cannot be deleted.
    """
    # Verify user is sponsor representative
    su = sponsor_user.get_by_user_and_sponsor(
        db, user_id=current_user.sub, sponsor_id=sponsor_id
    )
    if not su or not su.is_active or not su.can_message_attendees:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized"
        )

    campaign = sponsor_campaign.get(db, campaign_id=campaign_id)
    if not campaign or campaign.sponsor_id != sponsor_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Campaign not found"
        )

    try:
        sponsor_campaign.delete(db, campaign_id=campaign_id)
        return {"message": "Campaign deleted successfully"}
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


# Tracking endpoints (for open and click tracking)
# These are public endpoints accessed from email links/pixels

@router.get("/campaigns/track/open/{delivery_id}.png")
async def track_email_open(
    delivery_id: str,
    db: Session = Depends(get_db),
):
    """
    Track email open via 1x1 transparent tracking pixel.

    This endpoint is called when the recipient opens the email.
    Returns a 1x1 transparent PNG image.
    """
    from fastapi.responses import Response

    print(f"[TRACKING] Open tracking request for delivery: {delivery_id}")

    try:
        # Track the open - returns (delivery, is_first_open)
        delivery, is_first_open = campaign_delivery.track_open(db, delivery_id=delivery_id)

        if delivery:
            print(f"[TRACKING] Open tracked for delivery {delivery_id}, first_open={is_first_open}, campaign={delivery.campaign_id}")
            # Update campaign stats if this is the first open
            if is_first_open:
                sponsor_campaign.increment_opened_count(db, campaign_id=delivery.campaign_id)
                print(f"[TRACKING] Campaign {delivery.campaign_id} opened_count incremented")
        else:
            print(f"[TRACKING] WARNING: Delivery not found for open tracking: {delivery_id}")
    except Exception as e:
        print(f"[TRACKING] ERROR tracking open for {delivery_id}: {e}")

    # Return 1x1 transparent PNG (always return pixel even if tracking fails)
    transparent_pixel = bytes.fromhex('89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4890000000a49444154789c6300010000050001ad7a0ac00000000049454e44ae426082')

    return Response(content=transparent_pixel, media_type="image/png")


@router.get("/campaigns/track/click/{delivery_id}")
async def track_email_click(
    delivery_id: str,
    url: str,
    db: Session = Depends(get_db),
):
    """
    Track link click and redirect to target URL.

    Usage: Replace links in email with:
    /campaigns/track/click/{delivery_id}?url={target_url}
    """
    from fastapi.responses import RedirectResponse

    print(f"[TRACKING] Click tracking request for delivery: {delivery_id}, url: {url}")

    try:
        # Track the click - returns (delivery, is_first_click)
        delivery, is_first_click = campaign_delivery.track_click(db, delivery_id=delivery_id)

        if delivery:
            print(f"[TRACKING] Click tracked for delivery {delivery_id}, first_click={is_first_click}, campaign={delivery.campaign_id}")
            # Update campaign stats if this is the first click
            if is_first_click:
                sponsor_campaign.increment_clicked_count(db, campaign_id=delivery.campaign_id)
                print(f"[TRACKING] Campaign {delivery.campaign_id} clicked_count incremented")
        else:
            print(f"[TRACKING] WARNING: Delivery not found for click tracking: {delivery_id}")
    except Exception as e:
        print(f"[TRACKING] ERROR tracking click for {delivery_id}: {e}")

    # Redirect to target URL (always redirect even if tracking fails)
    return RedirectResponse(url=url)


# AI-Powered Message Generation
# These endpoints provide AI-generated campaign messages

class AIGenerationRequest(BaseModel):
    """Request schema for AI message generation."""
    audience_type: str
    campaign_goal: Optional[str] = None
    tone: str = "professional"  # professional, casual, friendly
    include_cta: bool = True


class AIGenerationResponse(BaseModel):
    """Response schema for AI-generated messages."""
    subject: str
    body: str
    reasoning: str
    suggestions: List[str]


@router.post("/sponsors/{sponsor_id}/campaigns/generate-ai-message", response_model=AIGenerationResponse)
@limiter.limit("20/minute")
async def generate_ai_message(
    request: Request,
    sponsor_id: str,
    ai_request: AIGenerationRequest,
    db: Session = Depends(get_db),
    current_user: TokenPayload = Depends(deps.get_current_user),
):
    """
    Generate AI-powered campaign message using Claude.

    This endpoint uses Claude AI to generate personalized, context-aware
    campaign messages based on the event, sponsor, and target audience.

    Features:
    - Context-aware generation (uses event details, sponsor info)
    - Multiple tone options (professional, casual, friendly)
    - Personalization variable suggestions
    - Best practice recommendations

    Permissions:
    - User must be an active sponsor representative
    - ANTHROPIC_API_KEY must be configured
    """
    # Check if AI is available
    if not ai_generator.is_available():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AI message generation is not available. Please contact support."
        )

    # Verify user is sponsor representative
    su = sponsor_user.get_by_user_and_sponsor(
        db, user_id=current_user.sub, sponsor_id=sponsor_id
    )
    if not su or not su.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized"
        )

    # Get sponsor details
    sponsor_obj = sponsor.get(db, id=sponsor_id)
    if not sponsor_obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Sponsor not found"
        )

    # Get event details
    event_obj = event.get(db, id=sponsor_obj.event_id) if sponsor_obj.event_id else None

    try:
        # Generate message using Claude AI
        result = ai_generator.generate_campaign_message(
            event_name=event_obj.name if event_obj else "Your Event",
            event_description=event_obj.description if event_obj else None,
            event_start_date=event_obj.start_date.isoformat() if event_obj and event_obj.start_date else None,
            event_end_date=event_obj.end_date.isoformat() if event_obj and event_obj.end_date else None,
            sponsor_name=sponsor_obj.company_name or "Your Company",
            sponsor_description=sponsor_obj.company_description,
            audience_type=ai_request.audience_type,
            campaign_goal=ai_request.campaign_goal,
            tone=ai_request.tone,
            include_cta=ai_request.include_cta,
        )

        return AIGenerationResponse(**result)

    except Exception as e:
        logger.error(f"AI generation failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"AI generation failed: {str(e)}"
        )


@router.post("/sponsors/{sponsor_id}/campaigns/generate-subject-variations")
@limiter.limit("10/minute")
async def generate_subject_variations(
    request: Request,
    sponsor_id: str,
    base_subject: str,
    count: int = 3,
    db: Session = Depends(get_db),
    current_user: TokenPayload = Depends(deps.get_current_user),
):
    """
    Generate variations of a subject line for A/B testing.

    Returns multiple variations of the same subject line with different
    approaches (question vs statement, curiosity vs benefit, etc.)
    """
    if not ai_generator.is_available():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AI generation not available"
        )

    # Verify user is sponsor representative
    su = sponsor_user.get_by_user_and_sponsor(
        db, user_id=current_user.sub, sponsor_id=sponsor_id
    )
    if not su or not su.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized"
        )

    try:
        variations = ai_generator.generate_subject_variations(
            base_subject=base_subject,
            count=min(count, 5)  # Max 5 variations
        )

        return {"variations": variations}

    except Exception as e:
        logger.error(f"Subject variation generation failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Generation failed: {str(e)}"
        )


# ============================================================================
# Email Unsubscribe & Preferences Endpoints
# These are public endpoints accessed from email footer links
# ============================================================================

class EmailPreferencesUpdate(BaseModel):
    """Request schema for updating email preferences."""
    sponsor_emails: bool = True
    event_updates: bool = True
    platform_news: bool = True


class EmailPreferencesResponse(BaseModel):
    """Response schema for email preferences."""
    sponsor_emails: bool
    event_updates: bool
    platform_news: bool
    sponsor_name: Optional[str] = None


@router.post("/unsubscribe/{delivery_id}")
async def unsubscribe_from_emails(
    delivery_id: str,
    db: Session = Depends(get_db),
):
    """
    Unsubscribe from sponsor emails (public endpoint).

    This endpoint is called from the unsubscribe link in campaign emails.
    It marks the recipient as unsubscribed from the sponsor's mailing list.
    """
    # Get the delivery record
    delivery = campaign_delivery.get(db, delivery_id=delivery_id)
    if not delivery:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invalid unsubscribe link"
        )

    # Mark as unsubscribed
    try:
        campaign_delivery.mark_unsubscribed(db, delivery_id=delivery_id)
        logger.info(f"User unsubscribed via delivery {delivery_id}")
        return {"message": "Successfully unsubscribed"}
    except Exception as e:
        logger.error(f"Unsubscribe failed for {delivery_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process unsubscribe request"
        )


@router.get("/email-preferences/{delivery_id}", response_model=EmailPreferencesResponse)
async def get_email_preferences(
    delivery_id: str,
    db: Session = Depends(get_db),
):
    """
    Get current email preferences for a recipient (public endpoint).

    Returns the recipient's current email preferences based on the delivery record.
    """
    # Get the delivery record
    delivery = campaign_delivery.get(db, delivery_id=delivery_id)
    if not delivery:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invalid preferences link"
        )

    # Get sponsor name from the campaign
    sponsor_name = None
    if delivery.campaign and delivery.campaign.sponsor:
        sponsor_name = delivery.campaign.sponsor.company_name

    # Return current preferences (defaults to opted-in for now)
    # In a full implementation, you'd store these preferences per-lead
    return EmailPreferencesResponse(
        sponsor_emails=not delivery.unsubscribed_at,  # False if unsubscribed
        event_updates=True,
        platform_news=True,
        sponsor_name=sponsor_name,
    )


@router.put("/email-preferences/{delivery_id}")
async def update_email_preferences(
    delivery_id: str,
    preferences: EmailPreferencesUpdate,
    db: Session = Depends(get_db),
):
    """
    Update email preferences for a recipient (public endpoint).

    Allows recipients to manage their email preferences from the email footer link.
    """
    # Get the delivery record
    delivery = campaign_delivery.get(db, delivery_id=delivery_id)
    if not delivery:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invalid preferences link"
        )

    try:
        # If sponsor_emails is disabled, mark as unsubscribed
        if not preferences.sponsor_emails:
            campaign_delivery.mark_unsubscribed(db, delivery_id=delivery_id)
        else:
            # If re-subscribing, clear the unsubscribed flag
            campaign_delivery.clear_unsubscribed(db, delivery_id=delivery_id)

        logger.info(f"Email preferences updated for delivery {delivery_id}")
        return {"message": "Preferences updated successfully"}
    except Exception as e:
        logger.error(f"Failed to update preferences for {delivery_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update preferences"
        )
