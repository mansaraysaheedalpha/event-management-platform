# app/crud/crud_sponsor_campaign.py
"""
CRUD operations for sponsor campaigns.

Production features:
- Audience filtering with SQL optimization
- Batch lead fetching
- Campaign status management
- Analytics aggregation
"""

from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_, Integer
from app.models.sponsor_campaign import SponsorCampaign
from app.models.campaign_delivery import CampaignDelivery
from app.models.sponsor_lead import SponsorLead
from app.schemas.sponsor_campaign import CampaignCreate, CampaignUpdate
from datetime import datetime
import uuid


class CRUDSponsorCampaign:
    """CRUD operations for sponsor campaigns."""

    def create(
        self,
        db: Session,
        *,
        sponsor_id: str,
        event_id: str,
        created_by_user_id: str,
        created_by_user_name: Optional[str],
        obj_in: CampaignCreate
    ) -> SponsorCampaign:
        """Create a new campaign in draft status."""
        campaign = SponsorCampaign(
            id=f"spcmpn_{uuid.uuid4().hex[:12]}",
            sponsor_id=sponsor_id,
            event_id=event_id,
            name=obj_in.name,
            subject=obj_in.subject,
            message_body=obj_in.message_body,
            audience_type=obj_in.audience_type,
            audience_filter=obj_in.audience_filter,
            scheduled_at=obj_in.scheduled_at,
            created_by_user_id=created_by_user_id,
            created_by_user_name=created_by_user_name,
            campaign_metadata=obj_in.campaign_metadata or {},
            status="draft",
        )
        db.add(campaign)
        db.commit()
        db.refresh(campaign)
        return campaign

    def get(self, db: Session, campaign_id: str) -> Optional[SponsorCampaign]:
        """Get campaign by ID."""
        return db.query(SponsorCampaign).filter(SponsorCampaign.id == campaign_id).first()

    def get_by_sponsor(
        self,
        db: Session,
        sponsor_id: str,
        *,
        skip: int = 0,
        limit: int = 100,
        status: Optional[str] = None
    ) -> List[SponsorCampaign]:
        """Get all campaigns for a sponsor with optional filtering."""
        query = db.query(SponsorCampaign).filter(SponsorCampaign.sponsor_id == sponsor_id)

        if status:
            query = query.filter(SponsorCampaign.status == status)

        return query.order_by(SponsorCampaign.created_at.desc()).offset(skip).limit(limit).all()

    def count_by_sponsor(
        self,
        db: Session,
        sponsor_id: str,
        *,
        status: Optional[str] = None
    ) -> int:
        """Count campaigns for a sponsor."""
        query = db.query(func.count(SponsorCampaign.id)).filter(
            SponsorCampaign.sponsor_id == sponsor_id
        )

        if status:
            query = query.filter(SponsorCampaign.status == status)

        return query.scalar()

    def update(
        self,
        db: Session,
        *,
        campaign: SponsorCampaign,
        obj_in: CampaignUpdate
    ) -> SponsorCampaign:
        """Update campaign (only allowed in draft status)."""
        if campaign.status != "draft":
            raise ValueError("Can only update campaigns in draft status")

        update_data = obj_in.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(campaign, field, value)

        campaign.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(campaign)
        return campaign

    def delete(self, db: Session, *, campaign_id: str) -> bool:
        """Delete campaign (only allowed in draft status)."""
        campaign = self.get(db, campaign_id)
        if not campaign:
            return False

        if campaign.status != "draft":
            raise ValueError("Can only delete campaigns in draft status")

        db.delete(campaign)
        db.commit()
        return True

    def get_recipients(
        self,
        db: Session,
        *,
        sponsor_id: str,
        audience_type: str,
        audience_filter: Optional[Dict[str, Any]] = None
    ) -> List[SponsorLead]:
        """
        Get list of leads based on audience filter.

        Audience types:
        - all: All leads
        - hot: intent_level = 'hot'
        - warm: intent_level = 'warm'
        - cold: intent_level = 'cold'
        - new: follow_up_status = 'new'
        - contacted: follow_up_status != 'new'
        - custom: Use audience_filter dict
        """
        query = db.query(SponsorLead).filter(
            and_(
                SponsorLead.sponsor_id == sponsor_id,
                SponsorLead.is_archived == False,
                SponsorLead.user_email.isnot(None)  # Only leads with email
            )
        )

        # Apply audience filtering
        if audience_type == "hot":
            query = query.filter(SponsorLead.intent_level == "hot")
        elif audience_type == "warm":
            query = query.filter(SponsorLead.intent_level == "warm")
        elif audience_type == "cold":
            query = query.filter(SponsorLead.intent_level == "cold")
        elif audience_type == "new":
            query = query.filter(SponsorLead.follow_up_status == "new")
        elif audience_type == "contacted":
            query = query.filter(SponsorLead.follow_up_status != "new")
        elif audience_type == "custom" and audience_filter:
            # Apply custom filters
            if "intent_score_min" in audience_filter:
                query = query.filter(SponsorLead.intent_score >= audience_filter["intent_score_min"])
            if "intent_score_max" in audience_filter:
                query = query.filter(SponsorLead.intent_score <= audience_filter["intent_score_max"])
            if "tags" in audience_filter:
                # Filter by tags (JSON array contains)
                for tag in audience_filter["tags"]:
                    query = query.filter(SponsorLead.tags.contains([tag]))

        return query.all()

    def mark_queued(self, db: Session, *, campaign: SponsorCampaign, recipient_count: int):
        """Mark campaign as queued for sending."""
        campaign.status = "queued"
        campaign.total_recipients = recipient_count
        campaign.started_at = datetime.utcnow()
        campaign.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(campaign)

    def mark_sending(self, db: Session, *, campaign: SponsorCampaign):
        """Mark campaign as currently sending."""
        campaign.status = "sending"
        campaign.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(campaign)

    def mark_sent(self, db: Session, *, campaign: SponsorCampaign):
        """Mark campaign as completed."""
        campaign.status = "sent"
        campaign.completed_at = datetime.utcnow()
        campaign.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(campaign)

    def mark_failed(self, db: Session, *, campaign: SponsorCampaign, error: str):
        """Mark campaign as failed."""
        campaign.status = "failed"
        campaign.error_message = error
        campaign.completed_at = datetime.utcnow()
        campaign.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(campaign)

    def update_delivery_stats(self, db: Session, *, campaign_id: str):
        """Update campaign stats from delivery records."""
        # Aggregate delivery stats
        stats = db.query(
            func.count(CampaignDelivery.id).label('total'),
            func.sum(func.cast(CampaignDelivery.status == 'sent', Integer)).label('sent'),
            func.sum(func.cast(CampaignDelivery.status == 'delivered', Integer)).label('delivered'),
            func.sum(func.cast(CampaignDelivery.status.in_(['failed', 'bounced']), Integer)).label('failed'),
            func.sum(func.cast(CampaignDelivery.opened_at.isnot(None), Integer)).label('opened'),
            func.sum(func.cast(CampaignDelivery.first_click_at.isnot(None), Integer)).label('clicked'),
        ).filter(CampaignDelivery.campaign_id == campaign_id).first()

        # Update campaign
        campaign = self.get(db, campaign_id)
        if campaign and stats:
            campaign.sent_count = stats.sent or 0
            campaign.delivered_count = stats.delivered or 0
            campaign.failed_count = stats.failed or 0
            campaign.opened_count = stats.opened or 0
            campaign.clicked_count = stats.clicked or 0
            campaign.updated_at = datetime.utcnow()
            db.commit()

    def get_stats(self, db: Session, *, campaign_id: str) -> Dict[str, Any]:
        """Get comprehensive campaign statistics."""
        campaign = self.get(db, campaign_id)
        if not campaign:
            return {}

        # Get delivery breakdown
        delivery_stats = db.query(
            CampaignDelivery.status,
            func.count(CampaignDelivery.id).label('count')
        ).filter(
            CampaignDelivery.campaign_id == campaign_id
        ).group_by(CampaignDelivery.status).all()

        status_breakdown = {stat.status: stat.count for stat in delivery_stats}

        # Calculate rates
        sent = campaign.sent_count or 0
        delivery_rate = (campaign.delivered_count / sent * 100) if sent > 0 else 0
        open_rate = (campaign.opened_count / sent * 100) if sent > 0 else 0
        click_rate = (campaign.clicked_count / sent * 100) if sent > 0 else 0
        bounce_rate = (campaign.failed_count / sent * 100) if sent > 0 else 0

        return {
            "campaign_id": campaign.id,
            "total_recipients": campaign.total_recipients,
            "sent": sent,
            "delivered": campaign.delivered_count,
            "failed": campaign.failed_count,
            "opened": campaign.opened_count,
            "clicked": campaign.clicked_count,
            "delivery_rate": round(delivery_rate, 2),
            "open_rate": round(open_rate, 2),
            "click_rate": round(click_rate, 2),
            "bounce_rate": round(bounce_rate, 2),
            "status_breakdown": status_breakdown,
        }


# Create singleton instance
sponsor_campaign = CRUDSponsorCampaign()
