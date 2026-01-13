# app/background_tasks/analytics_tasks.py
"""
Background tasks for analytics and monetization.

Tasks include:
- Refreshing materialized views for analytics
- Cleaning up old analytics data
"""

import logging
from app.db.session import SessionLocal
from app.crud.crud_monetization_event import monetization_event
from sqlalchemy import text

logger = logging.getLogger(__name__)


def refresh_analytics_views():
    """
    Refresh all analytics materialized views.

    This task runs every 5 minutes to keep analytics data near real-time.

    Refreshes:
    - monetization_conversion_funnels
    - ad_analytics_daily
    """
    db = SessionLocal()

    try:
        logger.info("Starting analytics views refresh...")

        # Refresh monetization conversion funnels
        monetization_event.refresh_materialized_views(db)

        # Refresh ad analytics daily view (if exists)
        try:
            view_exists = db.execute(text("""
                SELECT EXISTS (
                    SELECT 1 FROM pg_matviews
                    WHERE matviewname = 'ad_analytics_daily'
                )
            """)).scalar()

            if view_exists:
                db.execute(text("REFRESH MATERIALIZED VIEW CONCURRENTLY ad_analytics_daily"))
                db.commit()
                logger.info("Successfully refreshed ad_analytics_daily")
            else:
                logger.debug("ad_analytics_daily view does not exist yet - skipping refresh")
        except Exception as e:
            logger.error(f"Error refreshing ad_analytics_daily: {e}")
            db.rollback()

        logger.info("Analytics views refresh completed successfully")

    except Exception as e:
        logger.error(f"Error in refresh_analytics_views: {e}")
        db.rollback()
    finally:
        db.close()


def cleanup_old_events():
    """
    Optional: Clean up old monetization events (older than 1 year).

    This helps maintain database performance by archiving or deleting
    old event data that's no longer needed for real-time analytics.

    Note: Adjust retention policy based on your requirements.
    """
    db = SessionLocal()

    try:
        logger.info("Starting cleanup of old monetization events...")

        # Example: Delete events older than 1 year
        # You might want to archive instead of delete
        query = text("""
            DELETE FROM monetization_events
            WHERE created_at < NOW() - INTERVAL '1 year'
        """)

        result = db.execute(query)
        db.commit()

        deleted_count = result.rowcount
        logger.info(f"Cleaned up {deleted_count} old monetization events")

    except Exception as e:
        logger.error(f"Error in cleanup_old_events: {e}")
        db.rollback()
    finally:
        db.close()
