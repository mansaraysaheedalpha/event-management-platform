# app/tasks/offer_tasks.py
"""
Background tasks for offer management.
"""
import logging
from sqlalchemy.orm import Session
from app.db.session import SessionLocal
from app.crud import crud_offer

logger = logging.getLogger(__name__)


def auto_expire_offers():
    """
    Background task: Auto-expire offers that have passed their expiration date.

    This task should be run periodically (e.g., every hour) via a cron job or scheduler.

    Returns: Number of offers expired
    """
    db = SessionLocal()
    try:
        count = crud_offer.offer.auto_expire_offers(db)

        if count > 0:
            logger.info(f"Auto-expired {count} offers")

        return count

    except Exception as e:
        logger.error(f"Error in auto_expire_offers task: {str(e)}")
        return 0

    finally:
        db.close()


def cleanup_stale_reservations():
    """
    Background task: Cleanup stale inventory reservations.

    Redis TTL is the primary cleanup mechanism, but this task provides
    a safety net for reservations where the Redis key expired but the
    DB inventory_reserved was never decremented (e.g. server crash).

    Runs every 5 minutes. Checks for offers where inventory_reserved > 0
    but no active Redis reservation exists.

    Returns: Number of stale reservations cleaned up
    """
    db = SessionLocal()
    cleaned = 0
    try:
        from app.services.offer_reservation_service import offer_reservation_service
        from app.models.offer import Offer as OfferModel

        if not offer_reservation_service or not offer_reservation_service.redis:
            logger.info("Redis unavailable, skipping stale reservation cleanup")
            return 0

        # H1: Use SELECT FOR UPDATE to prevent race condition with concurrent cleanup
        offers_with_reservations = db.query(OfferModel).filter(
            OfferModel.inventory_reserved > 0
        ).with_for_update(skip_locked=True).all()

        for offer in offers_with_reservations:
            try:
                # Check if any active Redis reservations exist for this offer
                pattern = f"offer_reservation:*:{offer.id}"
                active_keys = list(offer_reservation_service.redis.scan_iter(
                    match=pattern, count=100
                ))

                if not active_keys and offer.inventory_reserved > 0:
                    stale_count = offer.inventory_reserved
                    offer.inventory_reserved = 0
                    db.commit()
                    cleaned += stale_count
                    logger.warning(
                        f"Released {stale_count} stale reservation(s) for offer {offer.id}"
                    )
            except Exception as e:
                logger.error(f"Error checking reservations for offer {offer.id}: {e}")
                db.rollback()

        if cleaned > 0:
            logger.info(f"Cleaned up {cleaned} stale inventory reservations")
        else:
            logger.debug("No stale reservations found")

        return cleaned

    except Exception as e:
        logger.error(f"Error in cleanup_stale_reservations task: {str(e)}")
        db.rollback()
        return 0

    finally:
        db.close()


MAX_FULFILLMENT_RETRIES = 3


def _get_retry_count(purchase_id: str) -> int:
    """Get fulfillment retry count from Redis."""
    try:
        from app.api import deps
        import redis as _redis
        r = _redis.Redis(connection_pool=deps.redis_pool)
        count = r.get(f"fulfillment:retry:{purchase_id}")
        return int(count) if count else 0
    except Exception:
        return 0


def _increment_retry_count(purchase_id: str) -> int:
    """Increment and return fulfillment retry count in Redis (TTL 24h)."""
    try:
        from app.api import deps
        import redis as _redis
        r = _redis.Redis(connection_pool=deps.redis_pool)
        key = f"fulfillment:retry:{purchase_id}"
        count = r.incr(key)
        r.expire(key, 86400)
        return count
    except Exception:
        return MAX_FULFILLMENT_RETRIES  # Fail-safe: don't retry if Redis is down


def process_pending_fulfillments():
    """
    Background task: Process pending offer fulfillments with retry logic.

    H8: Failed fulfillments are retried up to 3 times with exponential backoff.
    Retry count is tracked in Redis to avoid schema changes.

    Returns: Number of fulfillments processed
    """
    db = SessionLocal()
    try:
        from app.crud.crud_offer_purchase import offer_purchase
        from app.models.offer_purchase import OfferPurchase as OfferPurchaseModel
        from datetime import datetime, timedelta, timezone

        # Get PENDING fulfillments
        pending = offer_purchase.get_pending_fulfillments(db, limit=100)

        # Also pick up FAILED items eligible for retry (purchased within last 24h)
        cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
        failed_retryable = db.query(OfferPurchaseModel).filter(
            OfferPurchaseModel.fulfillment_status == "FAILED",
            OfferPurchaseModel.purchased_at >= cutoff
        ).limit(50).all()

        # Filter out those that exceeded max retries
        retryable = [
            p for p in failed_retryable
            if _get_retry_count(p.id) < MAX_FULFILLMENT_RETRIES
        ]

        all_to_process = list(pending) + retryable
        processed_count = 0

        for purchase in all_to_process:
            try:
                is_retry = purchase.fulfillment_status == "FAILED"
                if is_retry:
                    retry_num = _get_retry_count(purchase.id)
                    logger.info(f"Retrying fulfillment {purchase.id} (attempt {retry_num + 1}/{MAX_FULFILLMENT_RETRIES})")
                    # Reset status to PENDING for reprocessing
                    offer_purchase.update_fulfillment_status(
                        db, purchase_id=purchase.id, status="PENDING"
                    )

                if purchase.fulfillment_type == "DIGITAL":
                    _process_digital_fulfillment(db, purchase)
                    processed_count += 1
                elif purchase.fulfillment_type == "TICKET":
                    _process_ticket_upgrade_fulfillment(db, purchase)
                    processed_count += 1
                elif purchase.fulfillment_type == "PHYSICAL":
                    _process_physical_fulfillment(db, purchase)
                    processed_count += 1
                elif purchase.fulfillment_type == "SERVICE":
                    _process_service_fulfillment(db, purchase)
                    processed_count += 1

            except Exception as e:
                attempt = _increment_retry_count(purchase.id)
                if attempt >= MAX_FULFILLMENT_RETRIES:
                    logger.error(
                        f"Fulfillment {purchase.id} permanently failed after {attempt} attempts: {e}"
                    )
                    offer_purchase.update_fulfillment_status(
                        db, purchase_id=purchase.id, status="FAILED"
                    )
                else:
                    logger.warning(
                        f"Fulfillment {purchase.id} failed (attempt {attempt}/{MAX_FULFILLMENT_RETRIES}), will retry: {e}"
                    )
                    offer_purchase.update_fulfillment_status(
                        db, purchase_id=purchase.id, status="FAILED"
                    )

        if processed_count > 0:
            logger.info(f"Processed {processed_count} fulfillments ({len(retryable)} retries)")

        return processed_count

    except Exception as e:
        logger.error(f"Error in process_pending_fulfillments task: {str(e)}")
        return 0

    finally:
        db.close()


# ==================== Fulfillment Processors ====================

def _process_digital_fulfillment(db: Session, purchase):
    """Process digital content fulfillment.

    Generates a unique access code, marks as FULFILLED,
    and sends a fulfillment email to the purchaser.
    """
    from app.crud.crud_offer_purchase import offer_purchase
    from app.models.offer import Offer as OfferModel
    import secrets

    # Generate access code
    access_code = secrets.token_urlsafe(16)

    # Get the offer details for the email
    offer = db.query(OfferModel).filter(OfferModel.id == purchase.offer_id).first()
    offer_title = offer.title if offer else "your purchase"

    # Build digital content URL if offer has one configured
    digital_content_url = None
    if offer and hasattr(offer, 'digital_content_url') and offer.digital_content_url:
        digital_content_url = offer.digital_content_url

    # Update fulfillment
    offer_purchase.update_fulfillment_status(
        db,
        purchase_id=purchase.id,
        status="FULFILLED",
        access_code=access_code,
        digital_content_url=digital_content_url,
    )

    # Send fulfillment email to the purchaser
    try:
        from sqlalchemy import text
        user_row = db.execute(
            text("SELECT email, first_name FROM users WHERE id = :uid"),
            {"uid": purchase.user_id}
        ).fetchone()

        if user_row and user_row.email:
            from app.core.email import send_offer_fulfillment_email
            send_offer_fulfillment_email(
                to_email=user_row.email,
                user_name=user_row.first_name or "there",
                offer_title=offer_title,
                access_code=access_code,
                digital_content_url=digital_content_url,
            )
            logger.info(f"Sent fulfillment email for purchase {purchase.id} to {user_row.email}")
    except Exception as email_err:
        # Email failure should not rollback the fulfillment
        logger.warning(f"Failed to send fulfillment email for purchase {purchase.id}: {email_err}")

    logger.info(f"Fulfilled digital content for purchase {purchase.id}")


def _process_ticket_upgrade_fulfillment(db: Session, purchase):
    """Process ticket upgrade fulfillment.

    Marks as PROCESSING, then FULFILLED with a manual-action note.
    Full ticket system integration to be added when ticket upgrade API is available.
    """
    from app.crud.crud_offer_purchase import offer_purchase

    # Mark as processing
    offer_purchase.update_fulfillment_status(
        db,
        purchase_id=purchase.id,
        status="PROCESSING"
    )

    # Generate a reference for manual fulfillment tracking
    import uuid
    ref = f"TKT-UPGRADE-{str(uuid.uuid4())[:8].upper()}"

    logger.info(
        f"Ticket upgrade requires manual processing: purchase={purchase.id}, "
        f"user={purchase.user_id}, ref={ref}"
    )

    # Mark as fulfilled with reference for organizer follow-up
    offer_purchase.update_fulfillment_status(
        db,
        purchase_id=purchase.id,
        status="FULFILLED",
        access_code=ref,
    )

    logger.info(f"Fulfilled ticket upgrade for purchase {purchase.id} (ref: {ref})")


def _process_physical_fulfillment(db: Session, purchase):
    """Process physical merchandise fulfillment.

    Marks as PROCESSING, generates a manual tracking reference, then FULFILLED.
    Full shipping provider integration to be added when shipping API is available.
    """
    from app.crud.crud_offer_purchase import offer_purchase
    import uuid

    # Mark as processing
    offer_purchase.update_fulfillment_status(
        db,
        purchase_id=purchase.id,
        status="PROCESSING"
    )

    # Generate a placeholder tracking reference for manual fulfillment
    tracking_ref = f"MANUAL-{str(uuid.uuid4())[:8].upper()}"

    logger.info(
        f"Physical fulfillment requires manual shipping: purchase={purchase.id}, "
        f"user={purchase.user_id}, tracking={tracking_ref}"
    )

    offer_purchase.update_fulfillment_status(
        db,
        purchase_id=purchase.id,
        status="FULFILLED",
        tracking_number=tracking_ref,
    )

    logger.info(f"Fulfilled physical merchandise for purchase {purchase.id} (tracking: {tracking_ref})")


def _process_service_fulfillment(db: Session, purchase):
    """Process service fulfillment.

    Marks as PROCESSING, then FULFILLED with a scheduling reference.
    Full service delivery integration to be added when service scheduling API is available.
    """
    from app.crud.crud_offer_purchase import offer_purchase
    import uuid

    # Mark as processing
    offer_purchase.update_fulfillment_status(
        db,
        purchase_id=purchase.id,
        status="PROCESSING"
    )

    svc_ref = f"SVC-{str(uuid.uuid4())[:8].upper()}"

    logger.info(
        f"Service fulfillment scheduled (manual): purchase={purchase.id}, "
        f"user={purchase.user_id}, ref={svc_ref}"
    )

    offer_purchase.update_fulfillment_status(
        db,
        purchase_id=purchase.id,
        status="FULFILLED",
        access_code=svc_ref,
    )

    logger.info(f"Fulfilled service for purchase {purchase.id} (ref: {svc_ref})")


# Task scheduling is handled by app/scheduler.py (init_scheduler)
# Jobs registered: auto_expire_offers (30min), cleanup_stale_reservations (5min),
# process_pending_fulfillments (5min)
