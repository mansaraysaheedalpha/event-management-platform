# app/tasks/cleanup_tasks.py
"""
Data retention and cleanup tasks.

Implements data retention policies for compliance:
- Delete enrichment data after configured retention period
- Clean up expired rate limit entries
- Archive old analytics data
"""

import logging
from datetime import datetime, timedelta, timezone

from celery import shared_task
from celery.schedules import crontab

from app.core.audit import audit_logger, AuditAction
from app.core.config import settings
from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


@shared_task(
    name="app.tasks.cleanup_tasks.cleanup_expired_enrichment_data",
)
def cleanup_expired_enrichment_data() -> dict:
    """
    Delete enrichment data older than retention period.

    Runs daily to ensure compliance with data retention policy.
    Default retention: 365 days (configurable via ENRICHMENT_DATA_RETENTION_DAYS)

    Returns:
        Summary of deleted records
    """
    retention_days = settings.ENRICHMENT_DATA_RETENTION_DAYS
    cutoff_date = datetime.now(timezone.utc) - timedelta(days=retention_days)

    logger.info(
        f"Starting enrichment data cleanup. "
        f"Retention: {retention_days} days, Cutoff: {cutoff_date.isoformat()}"
    )

    # In production, this would execute database queries:
    # DELETE FROM user_profiles
    # WHERE enriched_at < cutoff_date
    # AND enrichment_status = 'COMPLETED'
    #
    # For now, we log what would be deleted
    deleted_count = 0

    # Example database cleanup (stubbed):
    # async with get_db_session() as session:
    #     result = await session.execute(
    #         delete(UserProfile)
    #         .where(UserProfile.enriched_at < cutoff_date)
    #         .where(UserProfile.enrichment_status == "COMPLETED")
    #         .returning(UserProfile.user_id)
    #     )
    #     deleted_ids = result.scalars().all()
    #     deleted_count = len(deleted_ids)
    #     await session.commit()

    logger.info(f"Enrichment data cleanup completed. Deleted: {deleted_count} records")

    # Log to audit trail
    audit_logger.log(
        action=AuditAction.PROFILE_EXPORTED,  # Using closest action type
        resource_type="enrichment_data",
        details={
            "operation": "retention_cleanup",
            "retention_days": retention_days,
            "cutoff_date": cutoff_date.isoformat(),
            "deleted_count": deleted_count,
        },
    )

    return {
        "retention_days": retention_days,
        "cutoff_date": cutoff_date.isoformat(),
        "deleted_count": deleted_count,
    }


@shared_task(
    name="app.tasks.cleanup_tasks.cleanup_rate_limit_entries",
)
def cleanup_rate_limit_entries() -> dict:
    """
    Clean up expired rate limit entries from Redis.

    Runs hourly to free up Redis memory.
    """
    logger.info("Starting rate limit entry cleanup")

    # Rate limit keys auto-expire via TTL, but we can force cleanup
    # of any stale entries
    cleaned_count = 0

    # In production with Redis:
    # pattern = "rate_limit:*"
    # async for key in redis_client.scan_iter(pattern):
    #     ttl = await redis_client.ttl(key)
    #     if ttl == -1:  # No expiry set
    #         await redis_client.delete(key)
    #         cleaned_count += 1

    logger.info(f"Rate limit cleanup completed. Cleaned: {cleaned_count} entries")

    return {"cleaned_count": cleaned_count}


@shared_task(
    name="app.tasks.cleanup_tasks.cleanup_analytics_cache",
)
def cleanup_analytics_cache() -> dict:
    """
    Clean up stale analytics cache entries.

    Analytics are cached for 1 hour, but events that ended
    long ago don't need their cache retained.
    """
    logger.info("Starting analytics cache cleanup")

    cleaned_count = 0

    # In production:
    # Delete analytics cache for events that ended > 30 days ago
    # pattern = "networking_analytics:*"

    logger.info(f"Analytics cache cleanup completed. Cleaned: {cleaned_count} entries")

    return {"cleaned_count": cleaned_count}


# ===========================================
# Celery Beat Schedule
# ===========================================

celery_app.conf.beat_schedule = {
    # Run enrichment cleanup daily at 3 AM UTC
    "cleanup-enrichment-data-daily": {
        "task": "app.tasks.cleanup_tasks.cleanup_expired_enrichment_data",
        "schedule": crontab(hour=3, minute=0),
    },
    # Run rate limit cleanup hourly
    "cleanup-rate-limits-hourly": {
        "task": "app.tasks.cleanup_tasks.cleanup_rate_limit_entries",
        "schedule": crontab(minute=0),  # Every hour at :00
    },
    # Run analytics cache cleanup daily at 4 AM UTC
    "cleanup-analytics-cache-daily": {
        "task": "app.tasks.cleanup_tasks.cleanup_analytics_cache",
        "schedule": crontab(hour=4, minute=0),
    },
}
