# app/crud/crud_rfp_audit_log.py
"""
CRUD operations for RFP audit trail.
"""
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
from datetime import datetime, timezone

from app.models.rfp_audit_log import RFPAuditLog


def create_audit_entry(
    db: Session,
    *,
    rfp_id: str,
    user_id: str,
    action: str,
    old_state: Optional[str] = None,
    new_state: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
    rfp_venue_id: Optional[str] = None,
) -> RFPAuditLog:
    """Create an audit log entry."""
    entry = RFPAuditLog(
        rfp_id=rfp_id,
        rfp_venue_id=rfp_venue_id,
        user_id=user_id,
        action=action,
        old_state=old_state,
        new_state=new_state,
        action_metadata=metadata,  # Map parameter 'metadata' to column 'action_metadata'
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


def get_audit_log_for_rfp(
    db: Session,
    rfp_id: str,
    limit: int = 100,
) -> List[RFPAuditLog]:
    """Get audit trail for an RFP."""
    return (
        db.query(RFPAuditLog)
        .filter(RFPAuditLog.rfp_id == rfp_id)
        .order_by(RFPAuditLog.created_at.desc())
        .limit(limit)
        .all()
    )


def get_audit_log_for_user(
    db: Session,
    user_id: str,
    limit: int = 100,
) -> List[RFPAuditLog]:
    """Get audit trail for a user's actions."""
    return (
        db.query(RFPAuditLog)
        .filter(RFPAuditLog.user_id == user_id)
        .order_by(RFPAuditLog.created_at.desc())
        .limit(limit)
        .all()
    )


def get_recent_actions(
    db: Session,
    action: Optional[str] = None,
    limit: int = 100,
) -> List[RFPAuditLog]:
    """Get recent audit entries, optionally filtered by action."""
    query = db.query(RFPAuditLog)

    if action:
        query = query.filter(RFPAuditLog.action == action)

    return (
        query
        .order_by(RFPAuditLog.created_at.desc())
        .limit(limit)
        .all()
    )
