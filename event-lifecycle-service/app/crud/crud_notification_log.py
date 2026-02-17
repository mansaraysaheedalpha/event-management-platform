# app/crud/crud_notification_log.py
"""
CRUD operations for RFP notification delivery tracking.
"""
from typing import Optional, List
from sqlalchemy.orm import Session
from datetime import datetime, timezone

from app.models.notification_log import RFPNotification


def create_notification_log(
    db: Session,
    *,
    rfp_id: str,
    recipient_type: str,  # 'organizer' or 'venue_owner'
    recipient_id: str,
    recipient_identifier: Optional[str],
    channel: str,  # 'email', 'whatsapp', 'inapp'
    event_type: str,  # 'rfp.new_request', 'rfp.deadline_passed', etc.
    rfp_venue_id: Optional[str] = None,
) -> RFPNotification:
    """Create a notification log entry."""
    notif = RFPNotification(
        rfp_id=rfp_id,
        rfp_venue_id=rfp_venue_id,
        recipient_type=recipient_type,
        recipient_id=recipient_id,
        recipient_identifier=recipient_identifier,
        channel=channel,
        event_type=event_type,
        status="pending",
    )
    db.add(notif)
    db.commit()
    db.refresh(notif)
    return notif


def update_notification_status(
    db: Session,
    *,
    notif_id: str,
    status: str,  # 'sent', 'delivered', 'failed'
    external_id: Optional[str] = None,
    error: Optional[str] = None,
) -> Optional[RFPNotification]:
    """Update notification delivery status."""
    notif = db.query(RFPNotification).filter(RFPNotification.id == notif_id).first()
    if not notif:
        return None

    notif.status = status

    if status == "sent" and not notif.sent_at:
        notif.sent_at = datetime.now(timezone.utc)

    if status == "delivered" and not notif.delivered_at:
        notif.delivered_at = datetime.now(timezone.utc)

    if external_id:
        notif.external_id = external_id

    if error:
        notif.error_message = error

    db.commit()
    db.refresh(notif)
    return notif


def get_notifications_for_rfp(
    db: Session,
    rfp_id: str,
    channel: Optional[str] = None,
    status: Optional[str] = None,
) -> List[RFPNotification]:
    """Get all notifications for an RFP."""
    query = db.query(RFPNotification).filter(RFPNotification.rfp_id == rfp_id)

    if channel:
        query = query.filter(RFPNotification.channel == channel)

    if status:
        query = query.filter(RFPNotification.status == status)

    return query.order_by(RFPNotification.created_at.desc()).all()


def get_notifications_for_recipient(
    db: Session,
    recipient_id: str,
    channel: Optional[str] = None,
    limit: int = 50,
) -> List[RFPNotification]:
    """Get recent notifications for a recipient."""
    query = db.query(RFPNotification).filter(
        RFPNotification.recipient_id == recipient_id
    )

    if channel:
        query = query.filter(RFPNotification.channel == channel)

    return (
        query.order_by(RFPNotification.created_at.desc())
        .limit(limit)
        .all()
    )


def get_failed_notifications(
    db: Session,
    limit: int = 100,
) -> List[RFPNotification]:
    """Get recent failed notifications for debugging."""
    return (
        db.query(RFPNotification)
        .filter(RFPNotification.status == "failed")
        .order_by(RFPNotification.created_at.desc())
        .limit(limit)
        .all()
    )
