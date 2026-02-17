# app/api/v1/endpoints/rfp_notifications.py
"""
RFP notification delivery tracking endpoints.
"""
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.api import deps
from app.db.session import get_db
from app.crud import crud_notification_log
from app.schemas.token import TokenPayload

router = APIRouter()


class NotificationResponse(BaseModel):
    id: str
    rfp_id: str
    rfp_venue_id: Optional[str]
    recipient_type: str
    recipient_id: str
    recipient_identifier: Optional[str]
    channel: str
    event_type: str
    status: str
    external_id: Optional[str]
    error_message: Optional[str]
    sent_at: Optional[str]
    delivered_at: Optional[str]
    created_at: str

    model_config = {"from_attributes": True}


@router.get("/organizations/{orgId}/rfps/{rfpId}/notifications")
def get_rfp_notifications(
    orgId: str,
    rfpId: str,
    channel: Optional[str] = Query(default=None),
    status: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
    current_user: TokenPayload = Depends(deps.get_current_user),
) -> List[NotificationResponse]:
    """
    Get notification delivery log for an RFP.
    Shows all email, WhatsApp, and in-app notifications sent for this RFP.
    """
    # Check authorization
    if current_user.org_id != orgId:
        raise HTTPException(status_code=403, detail="Not authorized")

    # Verify RFP belongs to org
    from app.models.rfp import RFP
    rfp = db.query(RFP).filter(RFP.id == rfpId, RFP.organization_id == orgId).first()
    if not rfp:
        raise HTTPException(status_code=404, detail="RFP not found")

    # Get notifications
    notifications = crud_notification_log.get_notifications_for_rfp(
        db=db,
        rfp_id=rfpId,
        channel=channel,
        status=status,
    )

    return [
        NotificationResponse(
            id=str(n.id),
            rfp_id=n.rfp_id,
            rfp_venue_id=n.rfp_venue_id,
            recipient_type=n.recipient_type,
            recipient_id=n.recipient_id,
            recipient_identifier=n.recipient_identifier,
            channel=n.channel,
            event_type=n.event_type,
            status=n.status,
            external_id=n.external_id,
            error_message=n.error_message,
            sent_at=n.sent_at.isoformat() if n.sent_at else None,
            delivered_at=n.delivered_at.isoformat() if n.delivered_at else None,
            created_at=n.created_at.isoformat(),
        )
        for n in notifications
    ]


@router.get("/notifications/failed")
def get_failed_notifications(
    limit: int = Query(default=50, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: TokenPayload = Depends(deps.get_current_user),
) -> List[NotificationResponse]:
    """
    Get recent failed notifications for debugging (admin only).
    Useful for diagnosing delivery issues.
    """
    # TODO: Add admin role check here
    # For now, any authenticated user can view (change for production)

    notifications = crud_notification_log.get_failed_notifications(db=db, limit=limit)

    return [
        NotificationResponse(
            id=str(n.id),
            rfp_id=n.rfp_id,
            rfp_venue_id=n.rfp_venue_id,
            recipient_type=n.recipient_type,
            recipient_id=n.recipient_id,
            recipient_identifier=n.recipient_identifier,
            channel=n.channel,
            event_type=n.event_type,
            status=n.status,
            external_id=n.external_id,
            error_message=n.error_message,
            sent_at=n.sent_at.isoformat() if n.sent_at else None,
            delivered_at=n.delivered_at.isoformat() if n.delivered_at else None,
            created_at=n.created_at.isoformat(),
        )
        for n in notifications
    ]
