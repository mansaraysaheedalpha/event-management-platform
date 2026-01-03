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
from datetime import datetime, timezone

from app.background_tasks.waitlist_tasks import check_expired_offers, offer_spots_to_next_users
from app.background_tasks.analytics_tasks import refresh_analytics_views

logger = logging.getLogger(__name__)

# Global scheduler instance
scheduler = None


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
    # Runs every 1 hour
    scheduler.add_job(
        func=refresh_analytics_views,
        trigger=IntervalTrigger(hours=1),
        id='refresh_analytics_views',
        name='Refresh Analytics Materialized Views',
        replace_existing=True
    )
    logger.info("Scheduled job: refresh_analytics_views (every 1 hour)")

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
