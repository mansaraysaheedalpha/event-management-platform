# app/crud/crud_webhook_event.py
from typing import List, Optional
from datetime import datetime, timezone, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import and_

from app.crud.base import CRUDBase
from app.models.payment_webhook_event import PaymentWebhookEvent
from app.schemas.payment import WebhookEventCreate, WebhookEventUpdate, WebhookEventStatus


class CRUDWebhookEvent(CRUDBase[PaymentWebhookEvent, WebhookEventCreate, WebhookEventUpdate]):
    """CRUD operations for PaymentWebhookEvent model."""

    def get_by_provider_event_id(
        self, db: Session, *, provider_code: str, provider_event_id: str
    ) -> Optional[PaymentWebhookEvent]:
        """Get a webhook event by provider's event ID."""
        return (
            db.query(self.model)
            .filter(
                and_(
                    self.model.provider_code == provider_code,
                    self.model.provider_event_id == provider_event_id,
                )
            )
            .first()
        )

    def is_already_processed(
        self, db: Session, *, provider_code: str, provider_event_id: str
    ) -> bool:
        """Check if an event has already been processed."""
        event = self.get_by_provider_event_id(
            db, provider_code=provider_code, provider_event_id=provider_event_id
        )
        return event is not None and event.status == "processed"

    def create_event(
        self, db: Session, *, obj_in: WebhookEventCreate
    ) -> PaymentWebhookEvent:
        """Create a new webhook event record."""
        db_obj = PaymentWebhookEvent(
            provider_code=obj_in.provider_code,
            provider_event_id=obj_in.provider_event_id,
            provider_event_type=obj_in.provider_event_type,
            payload=obj_in.payload,
            signature_verified=obj_in.signature_verified,
            ip_address=obj_in.ip_address,
            status="pending",
        )
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def upsert_event(
        self, db: Session, *, obj_in: WebhookEventCreate
    ) -> PaymentWebhookEvent:
        """Create or update a webhook event record."""
        existing = self.get_by_provider_event_id(
            db,
            provider_code=obj_in.provider_code,
            provider_event_id=obj_in.provider_event_id,
        )

        if existing:
            # Update existing event
            existing.payload = obj_in.payload
            existing.signature_verified = obj_in.signature_verified
            existing.ip_address = obj_in.ip_address
            db.add(existing)
            db.commit()
            db.refresh(existing)
            return existing
        else:
            return self.create_event(db, obj_in=obj_in)

    def mark_processing(
        self, db: Session, *, event_id: str
    ) -> Optional[PaymentWebhookEvent]:
        """Mark an event as processing."""
        event = self.get(db, id=event_id)
        if not event:
            return None

        event.status = "processing"
        db.add(event)
        db.commit()
        db.refresh(event)
        return event

    def mark_processed(
        self,
        db: Session,
        *,
        event_id: str,
        related_payment_id: Optional[str] = None,
        related_order_id: Optional[str] = None,
        related_refund_id: Optional[str] = None,
    ) -> Optional[PaymentWebhookEvent]:
        """Mark an event as processed."""
        event = self.get(db, id=event_id)
        if not event:
            return None

        event.status = "processed"
        event.processed_at = datetime.now(timezone.utc)

        if related_payment_id:
            event.related_payment_id = related_payment_id
        if related_order_id:
            event.related_order_id = related_order_id
        if related_refund_id:
            event.related_refund_id = related_refund_id

        db.add(event)
        db.commit()
        db.refresh(event)
        return event

    def mark_failed(
        self,
        db: Session,
        *,
        event_id: str,
        error: str,
        retry_count: Optional[int] = None,
    ) -> Optional[PaymentWebhookEvent]:
        """Mark an event as failed and schedule retry."""
        event = self.get(db, id=event_id)
        if not event:
            return None

        event.status = "failed"
        event.processing_error = error

        if retry_count is not None:
            event.retry_count = retry_count
        else:
            event.retry_count += 1

        # Calculate next retry time with exponential backoff
        if event.retry_count < 5:
            base_delay = 60  # 1 minute
            delay = base_delay * (5 ** (event.retry_count - 1))  # 1m, 5m, 25m, 2h, 10h
            event.next_retry_at = datetime.now(timezone.utc) + timedelta(seconds=delay)

        db.add(event)
        db.commit()
        db.refresh(event)
        return event

    def mark_skipped(
        self, db: Session, *, event_id: str, reason: str
    ) -> Optional[PaymentWebhookEvent]:
        """Mark an event as skipped."""
        event = self.get(db, id=event_id)
        if not event:
            return None

        event.status = "skipped"
        event.processing_error = reason
        event.processed_at = datetime.now(timezone.utc)

        db.add(event)
        db.commit()
        db.refresh(event)
        return event

    def get_retryable_events(
        self, db: Session, *, limit: int = 100
    ) -> List[PaymentWebhookEvent]:
        """Get events that are due for retry."""
        now = datetime.now(timezone.utc)
        return (
            db.query(self.model)
            .filter(
                and_(
                    self.model.status == "failed",
                    self.model.retry_count < 5,
                    self.model.next_retry_at <= now,
                )
            )
            .limit(limit)
            .all()
        )

    def get_pending_events(
        self, db: Session, *, limit: int = 100
    ) -> List[PaymentWebhookEvent]:
        """Get pending events that need processing."""
        return (
            db.query(self.model)
            .filter(self.model.status == "pending")
            .order_by(self.model.received_at)
            .limit(limit)
            .all()
        )

    def get_events_by_type(
        self,
        db: Session,
        *,
        event_type: str,
        skip: int = 0,
        limit: int = 50,
    ) -> List[PaymentWebhookEvent]:
        """Get events by event type."""
        return (
            db.query(self.model)
            .filter(self.model.provider_event_type == event_type)
            .order_by(self.model.received_at.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )


webhook_event = CRUDWebhookEvent(PaymentWebhookEvent)
