# app/scheduler.py
"""
Background task scheduler for waitlist management and other periodic tasks.

Uses APScheduler to run periodic background jobs for:
- Expiring waitlist offers
- Offering spots to next users in queue
- Cleaning up stale data
"""

import logging
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger
from apscheduler.events import EVENT_JOB_ERROR, EVENT_JOB_MISSED
from datetime import datetime, timezone

from app.background_tasks.waitlist_tasks import check_expired_offers, offer_spots_to_next_users
from app.background_tasks.analytics_tasks import refresh_analytics_views
from app.background_tasks.session_reminder_tasks import (
    check_upcoming_sessions,
    send_pending_reminders,
    retry_failed_reminders,
)
from app.background_tasks.pre_event_email_tasks import (
    check_events_starting_tomorrow,
    send_pending_pre_event_emails,
    retry_failed_pre_event_emails,
)
from app.background_tasks.offer_tasks import (
    auto_expire_offers,
    cleanup_stale_reservations,
    process_pending_fulfillments,
)
from app.background_tasks.ad_tasks import (
    auto_expire_ads,
    refresh_ad_analytics,
    cleanup_old_ad_events,
)
from app.utils.graphql_rate_limit import cleanup_expired_entries

logger = logging.getLogger(__name__)

# Global scheduler instance
scheduler = None


def _on_job_error(event):
    """M-OBS3: Log scheduler job errors with full context."""
    job_id = event.job_id
    exc = event.exception
    tb = event.traceback
    logger.error(
        "Scheduled job FAILED: job_id=%s error=%s",
        job_id, exc,
        exc_info=(type(exc), exc, None) if exc else None,
    )
    if tb:
        logger.error("Traceback for job %s:\n%s", job_id, tb)


def _on_job_missed(event):
    """M-OBS3: Log when a scheduled job misses its execution window."""
    logger.warning(
        "Scheduled job MISSED: job_id=%s scheduled_run_time=%s",
        event.job_id,
        event.scheduled_run_time,
    )


def init_scheduler():
    """
    Initialize the background scheduler with all periodic tasks.

    This is called once when the application starts up.
    """
    global scheduler

    if scheduler is not None:
        logger.warning("Scheduler already initialized")
        return scheduler

    scheduler = BackgroundScheduler(
        timezone="UTC",
        job_defaults={
            'coalesce': True,  # Combine missed executions
            'max_instances': 1,  # Only one instance of each job at a time
            'misfire_grace_time': 60  # Allow 60 seconds grace period
        }
    )

    # Job 1: Check for expired waitlist offers
    # Runs every 1 minute
    scheduler.add_job(
        func=check_expired_offers,
        trigger=IntervalTrigger(minutes=1),
        id='check_expired_offers',
        name='Check Expired Waitlist Offers',
        replace_existing=True
    )
    logger.info("Scheduled job: check_expired_offers (every 1 minute)")

    # Job 2: Offer spots to next users in waitlist queue
    # Runs every 5 minutes
    scheduler.add_job(
        func=offer_spots_to_next_users,
        trigger=IntervalTrigger(minutes=5),
        id='offer_spots_to_next_users',
        name='Offer Waitlist Spots to Next Users',
        replace_existing=True
    )
    logger.info("Scheduled job: offer_spots_to_next_users (every 5 minutes)")

    # Job 3: Refresh analytics materialized views
    # Runs every 5 minutes for near real-time analytics
    scheduler.add_job(
        func=refresh_analytics_views,
        trigger=IntervalTrigger(minutes=5),
        id='refresh_analytics_views',
        name='Refresh Analytics Materialized Views',
        replace_existing=True
    )
    logger.info("Scheduled job: refresh_analytics_views (every 5 minutes)")

    # Job 4: Check for upcoming sessions and schedule reminders
    # Runs every 1 minute to catch sessions in reminder windows
    scheduler.add_job(
        func=check_upcoming_sessions,
        trigger=IntervalTrigger(minutes=1),
        id='check_upcoming_sessions',
        name='Check Upcoming Sessions for Reminders',
        replace_existing=True
    )
    logger.info("Scheduled job: check_upcoming_sessions (every 1 minute)")

    # Job 5: Send pending session reminder emails
    # Runs every 1 minute to process queued reminders
    scheduler.add_job(
        func=send_pending_reminders,
        trigger=IntervalTrigger(minutes=1),
        id='send_pending_reminders',
        name='Send Pending Session Reminders',
        replace_existing=True
    )
    logger.info("Scheduled job: send_pending_reminders (every 1 minute)")

    # Job 6: Retry failed reminder emails
    # Runs every 5 minutes for dead letter processing
    scheduler.add_job(
        func=retry_failed_reminders,
        trigger=IntervalTrigger(minutes=5),
        id='retry_failed_reminders',
        name='Retry Failed Session Reminders',
        replace_existing=True
    )
    logger.info("Scheduled job: retry_failed_reminders (every 5 minutes)")

    # ===== PRE-EVENT EMAIL JOBS =====

    # Job 7: Check for events starting tomorrow and queue pre-event emails
    # Runs daily at 9 AM UTC
    scheduler.add_job(
        func=check_events_starting_tomorrow,
        trigger=CronTrigger(hour=9, minute=0),
        id='check_events_starting_tomorrow',
        name='Check Events Starting Tomorrow for Pre-Event Emails',
        replace_existing=True
    )
    logger.info("Scheduled job: check_events_starting_tomorrow (daily at 9 AM UTC)")

    # Job 8: Send pending pre-event emails
    # Runs every 2 minutes to process queued pre-event emails
    scheduler.add_job(
        func=send_pending_pre_event_emails,
        trigger=IntervalTrigger(minutes=2),
        id='send_pending_pre_event_emails',
        name='Send Pending Pre-Event Emails',
        replace_existing=True
    )
    logger.info("Scheduled job: send_pending_pre_event_emails (every 2 minutes)")

    # Job 9: Retry failed pre-event emails
    # Runs every 10 minutes for dead letter processing
    scheduler.add_job(
        func=retry_failed_pre_event_emails,
        trigger=IntervalTrigger(minutes=10),
        id='retry_failed_pre_event_emails',
        name='Retry Failed Pre-Event Emails',
        replace_existing=True
    )
    logger.info("Scheduled job: retry_failed_pre_event_emails (every 10 minutes)")

    # ===== OFFER MANAGEMENT JOBS =====

    # Job 10: Auto-expire offers past their expiration date
    # Runs every 30 minutes
    scheduler.add_job(
        func=auto_expire_offers,
        trigger=IntervalTrigger(minutes=30),
        id='auto_expire_offers',
        name='Auto-Expire Offers Past Expiration Date',
        replace_existing=True
    )
    logger.info("Scheduled job: auto_expire_offers (every 30 minutes)")

    # Job 11: Cleanup stale inventory reservations
    # Runs every 5 minutes (Redis TTL is primary, this is safety net)
    scheduler.add_job(
        func=cleanup_stale_reservations,
        trigger=IntervalTrigger(minutes=5),
        id='cleanup_stale_reservations',
        name='Cleanup Stale Offer Inventory Reservations',
        replace_existing=True
    )
    logger.info("Scheduled job: cleanup_stale_reservations (every 5 minutes)")

    # Job 12: Process pending offer fulfillments
    # Runs every 5 minutes
    scheduler.add_job(
        func=process_pending_fulfillments,
        trigger=IntervalTrigger(minutes=5),
        id='process_pending_fulfillments',
        name='Process Pending Offer Fulfillments',
        replace_existing=True
    )
    logger.info("Scheduled job: process_pending_fulfillments (every 5 minutes)")

    # ===== AD MANAGEMENT JOBS =====

    # Job 13: Auto-expire ads past their end date
    # Runs every 1 hour
    scheduler.add_job(
        func=auto_expire_ads,
        trigger=IntervalTrigger(hours=1),
        id='auto_expire_ads',
        name='Auto-Expire Ads Past End Date',
        replace_existing=True
    )
    logger.info("Scheduled job: auto_expire_ads (every 1 hour)")

    # Job 14: Refresh ad analytics materialized view
    # Runs every 1 hour
    scheduler.add_job(
        func=refresh_ad_analytics,
        trigger=IntervalTrigger(hours=1),
        id='refresh_ad_analytics',
        name='Refresh Ad Analytics Materialized View',
        replace_existing=True
    )
    logger.info("Scheduled job: refresh_ad_analytics (every 1 hour)")

    # Job 15: Cleanup old ad events (older than 90 days)
    # Runs daily at 2 AM UTC
    scheduler.add_job(
        func=cleanup_old_ad_events,
        trigger=CronTrigger(hour=2, minute=0),
        id='cleanup_old_ad_events',
        name='Cleanup Old Ad Events (90+ days)',
        replace_existing=True
    )
    logger.info("Scheduled job: cleanup_old_ad_events (daily at 2 AM UTC)")

    # ===== RATE LIMIT CLEANUP JOB =====

    # Job 16: Cleanup expired rate limit entries
    # Runs every 1 hour to prevent memory leaks
    scheduler.add_job(
        func=cleanup_expired_entries,
        trigger=IntervalTrigger(hours=1),
        id='cleanup_rate_limits',
        name='Cleanup Expired Rate Limit Entries',
        replace_existing=True
    )
    logger.info("Scheduled job: cleanup_rate_limits (every 1 hour)")

    # M-OBS3: Listen for job errors and misfires so they don't fail silently
    scheduler.add_listener(_on_job_error, EVENT_JOB_ERROR)
    scheduler.add_listener(_on_job_missed, EVENT_JOB_MISSED)

    # Start the scheduler
    scheduler.start()
    logger.info("Background scheduler started successfully")

    return scheduler


def shutdown_scheduler():
    """
    Gracefully shutdown the scheduler.

    This is called when the application shuts down.
    """
    global scheduler

    if scheduler is not None:
        scheduler.shutdown(wait=True)
        logger.info("Background scheduler shutdown complete")
        scheduler = None


def get_scheduler():
    """
    Get the global scheduler instance.

    Returns:
        BackgroundScheduler instance or None if not initialized
    """
    return scheduler


def get_scheduler_status():
    """
    Get the current status of all scheduled jobs.

    Returns:
        List of job details with next run time, status, etc.
    """
    global scheduler

    if scheduler is None:
        return {"status": "not_initialized", "jobs": []}

    jobs = []
    for job in scheduler.get_jobs():
        jobs.append({
            "id": job.id,
            "name": job.name,
            "next_run_time": job.next_run_time.isoformat() if job.next_run_time else None,
            "trigger": str(job.trigger)
        })

    return {
        "status": "running" if scheduler.running else "stopped",
        "jobs": jobs
    }
