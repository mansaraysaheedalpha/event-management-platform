# app/crud/crud_audit_log.py
from typing import List, Optional, Any, Dict
from datetime import datetime, timezone
from sqlalchemy.orm import Session

from app.models.payment_audit_log import PaymentAuditLog
from app.schemas.payment import AuditLogCreate


class CRUDAuditLog:
    """
    CRUD operations for PaymentAuditLog model.

    Note: This is a special CRUD class that only allows create and read operations.
    Audit logs are immutable and cannot be updated or deleted.
    """

    def __init__(self, model):
        self.model = model

    def get(self, db: Session, *, id: str) -> Optional[PaymentAuditLog]:
        """Get an audit log entry by ID."""
        return db.query(self.model).filter(self.model.id == id).first()

    def create(
        self, db: Session, *, obj_in: AuditLogCreate
    ) -> PaymentAuditLog:
        """Create a new audit log entry."""
        db_obj = PaymentAuditLog(
            action=obj_in.action,
            actor_type=obj_in.actor_type,
            actor_id=obj_in.actor_id,
            actor_ip=obj_in.actor_ip,
            actor_user_agent=obj_in.actor_user_agent,
            entity_type=obj_in.entity_type,
            entity_id=obj_in.entity_id,
            previous_state=obj_in.previous_state,
            new_state=obj_in.new_state,
            change_details=obj_in.change_details,
            organization_id=obj_in.organization_id,
            event_id=obj_in.event_id,
            request_id=obj_in.request_id,
        )
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def log_action(
        self,
        db: Session,
        *,
        action: str,
        actor_type: str,
        entity_type: str,
        entity_id: str,
        actor_id: Optional[str] = None,
        actor_ip: Optional[str] = None,
        actor_user_agent: Optional[str] = None,
        previous_state: Optional[Dict[str, Any]] = None,
        new_state: Optional[Dict[str, Any]] = None,
        change_details: Optional[Dict[str, Any]] = None,
        organization_id: Optional[str] = None,
        event_id: Optional[str] = None,
        request_id: Optional[str] = None,
    ) -> PaymentAuditLog:
        """Convenience method to log an action."""
        obj_in = AuditLogCreate(
            action=action,
            actor_type=actor_type,
            actor_id=actor_id,
            actor_ip=actor_ip,
            actor_user_agent=actor_user_agent,
            entity_type=entity_type,
            entity_id=entity_id,
            previous_state=previous_state,
            new_state=new_state,
            change_details=change_details,
            organization_id=organization_id,
            event_id=event_id,
            request_id=request_id,
        )
        return self.create(db, obj_in=obj_in)

    def get_by_entity(
        self,
        db: Session,
        *,
        entity_type: str,
        entity_id: str,
        skip: int = 0,
        limit: int = 100,
    ) -> List[PaymentAuditLog]:
        """Get audit logs for a specific entity."""
        return (
            db.query(self.model)
            .filter(
                self.model.entity_type == entity_type,
                self.model.entity_id == entity_id,
            )
            .order_by(self.model.created_at.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_by_organization(
        self,
        db: Session,
        *,
        organization_id: str,
        action: Optional[str] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> List[PaymentAuditLog]:
        """Get audit logs for an organization."""
        query = db.query(self.model).filter(
            self.model.organization_id == organization_id
        )

        if action:
            query = query.filter(self.model.action == action)

        return (
            query.order_by(self.model.created_at.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_by_actor(
        self,
        db: Session,
        *,
        actor_type: str,
        actor_id: Optional[str] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> List[PaymentAuditLog]:
        """Get audit logs by actor."""
        query = db.query(self.model).filter(self.model.actor_type == actor_type)

        if actor_id:
            query = query.filter(self.model.actor_id == actor_id)

        return (
            query.order_by(self.model.created_at.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_by_request_id(
        self, db: Session, *, request_id: str
    ) -> List[PaymentAuditLog]:
        """Get all audit logs for a specific request."""
        return (
            db.query(self.model)
            .filter(self.model.request_id == request_id)
            .order_by(self.model.created_at)
            .all()
        )

    def get_recent(
        self,
        db: Session,
        *,
        organization_id: Optional[str] = None,
        limit: int = 50,
    ) -> List[PaymentAuditLog]:
        """Get recent audit logs."""
        query = db.query(self.model)

        if organization_id:
            query = query.filter(self.model.organization_id == organization_id)

        return query.order_by(self.model.created_at.desc()).limit(limit).all()


audit_log = CRUDAuditLog(PaymentAuditLog)
