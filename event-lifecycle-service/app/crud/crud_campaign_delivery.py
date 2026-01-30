# app/crud/crud_campaign_delivery.py
"""
CRUD operations for campaign deliveries.

This tracks individual email sends per lead in a campaign.
"""

from typing import Optional, List
from sqlalchemy.orm import Session
from sqlalchemy import and_
from app.models.campaign_delivery import CampaignDelivery
from datetime import datetime
import uuid


class CRUDCampaignDelivery:
    """CRUD operations for campaign deliveries."""

    def create(
        self,
        db: Session,
        *,
        campaign_id: str,
        lead_id: str,
        recipient_email: str,
        recipient_name: Optional[str],
        personalized_subject: str,
        personalized_body: str
    ) -> CampaignDelivery:
        """Create a delivery record for a campaign recipient."""
        delivery = CampaignDelivery(
            id=f"spdlvr_{uuid.uuid4().hex[:12]}",
            campaign_id=campaign_id,
            lead_id=lead_id,
            recipient_email=recipient_email,
            recipient_name=recipient_name,
            personalized_subject=personalized_subject,
            personalized_body=personalized_body,
            status="pending",
        )
        db.add(delivery)
        db.commit()
        db.refresh(delivery)
        return delivery

    def get(self, db: Session, delivery_id: str) -> Optional[CampaignDelivery]:
        """Get delivery by ID."""
        return db.query(CampaignDelivery).filter(CampaignDelivery.id == delivery_id).first()

    def get_by_campaign(
        self,
        db: Session,
        campaign_id: str,
        *,
        skip: int = 0,
        limit: int = 100,
        status: Optional[str] = None
    ) -> List[CampaignDelivery]:
        """Get deliveries for a campaign."""
        query = db.query(CampaignDelivery).filter(CampaignDelivery.campaign_id == campaign_id)

        if status:
            query = query.filter(CampaignDelivery.status == status)

        return query.order_by(CampaignDelivery.queued_at.desc()).offset(skip).limit(limit).all()

    def get_by_lead(
        self,
        db: Session,
        lead_id: str,
        *,
        skip: int = 0,
        limit: int = 10
    ) -> List[CampaignDelivery]:
        """Get all deliveries sent to a specific lead."""
        return (
            db.query(CampaignDelivery)
            .filter(CampaignDelivery.lead_id == lead_id)
            .order_by(CampaignDelivery.queued_at.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

    def mark_sent(
        self,
        db: Session,
        *,
        delivery_id: str,
        provider_message_id: str,
        provider_response: Optional[str] = None
    ):
        """Mark delivery as sent."""
        delivery = self.get(db, delivery_id)
        if delivery:
            delivery.status = "sent"
            delivery.sent_at = datetime.utcnow()
            delivery.provider_message_id = provider_message_id
            delivery.provider_response = provider_response
            db.commit()
            db.refresh(delivery)
        return delivery

    def mark_delivered(self, db: Session, *, delivery_id: str):
        """Mark delivery as delivered (confirmation from email provider)."""
        delivery = self.get(db, delivery_id)
        if delivery:
            delivery.status = "delivered"
            delivery.delivered_at = datetime.utcnow()
            db.commit()
            db.refresh(delivery)
        return delivery

    def mark_failed(
        self,
        db: Session,
        *,
        delivery_id: str,
        error_message: str
    ):
        """Mark delivery as failed."""
        delivery = self.get(db, delivery_id)
        if delivery:
            delivery.status = "failed"
            delivery.error_message = error_message
            delivery.retry_count += 1
            delivery.last_retry_at = datetime.utcnow()
            db.commit()
            db.refresh(delivery)
        return delivery

    def mark_bounced(self, db: Session, *, delivery_id: str, error_message: str):
        """Mark delivery as bounced (email address invalid or rejecting)."""
        delivery = self.get(db, delivery_id)
        if delivery:
            delivery.status = "bounced"
            delivery.error_message = error_message
            db.commit()
            db.refresh(delivery)
        return delivery

    def track_open(self, db: Session, *, delivery_id: str) -> tuple[Optional["CampaignDelivery"], bool]:
        """
        Track email open.

        Returns:
            tuple: (delivery, is_first_open) - delivery record and whether this was the first open
        """
        delivery = self.get(db, delivery_id)
        is_first_open = False
        if delivery:
            if not delivery.opened_at:
                delivery.opened_at = datetime.utcnow()
                is_first_open = True
            delivery.opened_count += 1
            db.commit()
            db.refresh(delivery)
        return delivery, is_first_open

    def track_click(self, db: Session, *, delivery_id: str) -> tuple[Optional["CampaignDelivery"], bool]:
        """
        Track link click.

        Returns:
            tuple: (delivery, is_first_click) - delivery record and whether this was the first click
        """
        delivery = self.get(db, delivery_id)
        is_first_click = False
        if delivery:
            if not delivery.first_click_at:
                delivery.first_click_at = datetime.utcnow()
                is_first_click = True
            delivery.click_count += 1
            db.commit()
            db.refresh(delivery)
        return delivery, is_first_click

    def get_pending_deliveries(
        self,
        db: Session,
        campaign_id: str,
        *,
        limit: int = 50
    ) -> List[CampaignDelivery]:
        """Get pending deliveries for batch processing."""
        return (
            db.query(CampaignDelivery)
            .filter(
                and_(
                    CampaignDelivery.campaign_id == campaign_id,
                    CampaignDelivery.status == "pending",
                    CampaignDelivery.retry_count < 3  # Max 3 retries
                )
            )
            .limit(limit)
            .all()
        )

    def mark_unsubscribed(self, db: Session, *, delivery_id: str):
        """Mark recipient as unsubscribed from sponsor emails."""
        delivery = self.get(db, delivery_id)
        if delivery:
            delivery.unsubscribed_at = datetime.utcnow()
            db.commit()
            db.refresh(delivery)
        return delivery

    def clear_unsubscribed(self, db: Session, *, delivery_id: str):
        """Clear unsubscribed flag (re-subscribe)."""
        delivery = self.get(db, delivery_id)
        if delivery:
            delivery.unsubscribed_at = None
            db.commit()
            db.refresh(delivery)
        return delivery

    def is_unsubscribed(self, db: Session, *, lead_id: str, sponsor_id: str) -> bool:
        """Check if a lead has unsubscribed from a sponsor's emails."""
        from app.models.sponsor_campaign import SponsorCampaign

        # Check if any delivery from this sponsor to this lead has unsubscribed
        result = (
            db.query(CampaignDelivery)
            .join(SponsorCampaign, CampaignDelivery.campaign_id == SponsorCampaign.id)
            .filter(
                and_(
                    CampaignDelivery.lead_id == lead_id,
                    SponsorCampaign.sponsor_id == sponsor_id,
                    CampaignDelivery.unsubscribed_at.isnot(None)
                )
            )
            .first()
        )
        return result is not None


# Create singleton instance
campaign_delivery = CRUDCampaignDelivery()
