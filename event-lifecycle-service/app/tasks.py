# app/tasks.py
import os
import shutil
import json
import logging
from pathlib import Path
from pdf2image import convert_from_path
from sqlalchemy.orm import Session

from app.worker import celery_app
from app.db.session import SessionLocal
from app.db.redis import get_redis_client
from app.crud import crud_presentation
from app.core.config import settings
from app.core.s3 import get_s3_client

# Import all models to ensure SQLAlchemy can resolve relationships
import app.models  # noqa: F401

# Set up logging
logger = logging.getLogger(__name__)


@celery_app.task
def process_presentation(
    session_id: str,
    s3_key: str,
    user_id: str,
    original_filename: str = "presentation.pdf",
):
    """
    Celery task to download a PDF, convert it to images, upload them back,
    update the database, and publish a notification to Redis.

    Args:
        session_id: The session ID this presentation belongs to
        s3_key: The S3 key where the uploaded PDF is stored
        user_id: The ID of the user who uploaded the presentation
        original_filename: The original filename of the uploaded file (for download feature)
    """
    db: Session = SessionLocal()
    redis_client = get_redis_client()
    s3_client = get_s3_client()
    temp_dir = Path(f"/tmp/{session_id}")
    os.makedirs(temp_dir, exist_ok=True)
    temp_pdf_path = temp_dir / "original.pdf"

    slide_urls = []
    final_status = "processing"

    # Create presentation record with original file info for download feature
    presentation = crud_presentation.presentation.create_with_session(
        db,
        session_id=session_id,
        slide_urls=[],
        status="processing",
        original_file_key=s3_key,
        original_filename=original_filename,
    )

    try:
        # 1. Download the original PDF from S3
        s3_client.download_file(settings.AWS_S3_BUCKET_NAME, s3_key, str(temp_pdf_path))

        # 2. Convert PDF to images
        images = convert_from_path(str(temp_pdf_path), dpi=150)

        for i, image in enumerate(images):
            temp_image_path = temp_dir / f"slide_{i + 1}.jpg"
            image.save(temp_image_path, "JPEG", quality=85)

            # 3. Upload each slide image to S3
            public_s3_key = f"presentations/{session_id}/slide_{i + 1}.jpg"
            s3_client.upload_file(
                str(temp_image_path),
                settings.AWS_S3_BUCKET_NAME,
                public_s3_key,
                ExtraArgs={"ContentType": "image/jpeg"},
            )

            # Construct the public URL
            if settings.AWS_S3_ENDPOINT_URL:
                public_url = f"{settings.AWS_S3_ENDPOINT_URL}/{settings.AWS_S3_BUCKET_NAME}/{public_s3_key}"
                if "minio:9000" in public_url:
                    public_url = public_url.replace("minio:9000", "localhost:9000")
            else:
                public_url = f"https://{settings.AWS_S3_BUCKET_NAME}.s3.{settings.AWS_S3_REGION}.amazonaws.com/{public_s3_key}"

            slide_urls.append(public_url)

        # 4. Update the database with the final status and URLs
        if slide_urls:
            crud_presentation.presentation.update(
                db,
                db_obj=presentation,
                obj_in={"slide_urls": slide_urls, "status": "ready"},
            )
            final_status = "ready"
        else:
            raise ValueError("PDF processing resulted in zero slides.")

    except Exception as e:
        logger.error(
            f"Failed to process presentation for session {session_id}: {e}",
            exc_info=True,
        )
        final_status = "failed"
        crud_presentation.presentation.update(
            db, db_obj=presentation, obj_in={"status": "failed"}
        )

    finally:
        # 5. Publish the result to Redis for real-time notification
        try:
            message_payload = {
                "sessionId": session_id,
                "status": final_status,
                "userId": user_id,
            }
            redis_client.publish("presentation-events", json.dumps(message_payload))
            logger.info(
                f"Published presentation status for session {session_id}: {final_status}"
            )
        except Exception as e:
            logger.error(
                f"Failed to publish presentation status to Redis: {e}", exc_info=True
            )

        # 6. Clean up local files and database session
        shutil.rmtree(temp_dir, ignore_errors=True)
        db.close()

    return {"status": final_status}


# ── RFP System Tasks ──────────────────────────────────────────────────

@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
def process_rfp_deadlines(self):
    """
    Runs every 5 minutes. Checks for RFPs past deadline.
    - 'sent' with 0 responses → transition to 'expired'
    - 'collecting_responses' → transition to 'review'
    - Mark all non-responded venues as 'no_response'
    - Send deadline_passed notification to organizer
    """
    from datetime import datetime, timezone
    from sqlalchemy import func as sa_func
    from app.models.rfp import RFP
    from app.models.rfp_venue import RFPVenue

    db = SessionLocal()
    try:
        now = datetime.now(timezone.utc)

        # Find RFPs past deadline that haven't been processed yet
        expired_rfps = (
            db.query(RFP)
            .filter(
                RFP.status.in_(("sent", "collecting_responses")),
                RFP.response_deadline < now,
                RFP.deadline_processed_at.is_(None),  # NOT already processed
            )
            .all()
        )

        for rfp in expired_rfps:
            # Count responses
            total_venues = (
                db.query(sa_func.count(RFPVenue.id))
                .filter(RFPVenue.rfp_id == rfp.id)
                .scalar()
            )
            responded_count = (
                db.query(sa_func.count(RFPVenue.id))
                .filter(RFPVenue.rfp_id == rfp.id, RFPVenue.status == "responded")
                .scalar()
            )

            # Mark non-responded venues as no_response
            from app.crud.crud_rfp_venue import mark_no_response
            mark_no_response(db, rfp_id=rfp.id)

            if rfp.status == "sent" and responded_count == 0:
                rfp.status = "expired"
            else:
                rfp.status = "review"

            # Mark as processed BEFORE notification (idempotency)
            rfp.deadline_processed_at = now
            db.commit()

            # Send notification (if this fails and retries, the query won't pick up the RFP again)
            try:
                from app.utils.rfp_notifications import dispatch_deadline_passed_notification
                dispatch_deadline_passed_notification(db, rfp, responded_count, total_venues)
            except Exception as e:
                logger.warning(f"Failed to send deadline notification for RFP {rfp.id}: {e}")

        if expired_rfps:
            logger.info(f"Processed {len(expired_rfps)} RFP deadline(s)")

    except Exception as e:
        logger.error(f"process_rfp_deadlines failed: {e}", exc_info=True)
        self.retry(exc=e)
    finally:
        db.close()


@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
def send_rfp_deadline_reminders(self):
    """
    Runs every hour. Sends 24h-before reminders to non-responding venues.
    Uses a Redis key to avoid duplicate reminders.
    """
    from datetime import datetime, timezone, timedelta
    from app.models.rfp import RFP

    db = SessionLocal()
    redis = get_redis_client()
    try:
        now = datetime.now(timezone.utc)
        window_start = now + timedelta(hours=23)
        window_end = now + timedelta(hours=25)

        # Find RFPs with deadline in the 23-25 hour window
        rfps = (
            db.query(RFP)
            .filter(
                RFP.status.in_(("sent", "collecting_responses")),
                RFP.response_deadline >= window_start,
                RFP.response_deadline <= window_end,
            )
            .all()
        )

        for rfp in rfps:
            # Check if reminder already sent (avoid duplicates)
            reminder_key = f"rfp_reminder_sent:{rfp.id}"
            if redis.get(reminder_key):
                continue

            try:
                from app.utils.rfp_notifications import dispatch_deadline_reminder_notifications
                dispatch_deadline_reminder_notifications(db, rfp)
                # Mark as sent with 48h TTL (covers the window plus buffer)
                redis.setex(reminder_key, 48 * 3600, "1")
                logger.info(f"Sent deadline reminders for RFP {rfp.id}")
            except Exception as e:
                logger.warning(f"Failed to send reminders for RFP {rfp.id}: {e}")

    except Exception as e:
        logger.error(f"send_rfp_deadline_reminders failed: {e}", exc_info=True)
        self.retry(exc=e)
    finally:
        db.close()


@celery_app.task(bind=True, max_retries=3, default_retry_delay=120)
def refresh_exchange_rates(self):
    """
    Runs daily at 00:00 UTC. Fetches exchange rates for common currencies
    and caches them in Redis with 25-hour TTL.
    """
    from app.utils.exchange_rates import fetch_and_cache_rates

    currencies = ["USD", "KES", "NGN", "SLE", "ZAR", "GHS", "TZS", "UGX", "EUR", "GBP"]

    try:
        for currency in currencies:
            result = fetch_and_cache_rates(currency)
            if result:
                logger.info(f"Refreshed exchange rates for {currency}")
            else:
                logger.warning(f"Failed to refresh exchange rates for {currency}")

    except Exception as e:
        logger.error(f"refresh_exchange_rates failed: {e}", exc_info=True)
        self.retry(exc=e)
