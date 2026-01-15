# app/tasks/__init__.py
"""Background task definitions using Celery."""

from app.tasks.celery_app import celery_app
from app.tasks.enrichment_tasks import (
    enrich_user_task,
    queue_event_enrichments,
    retry_failed_enrichments,
)
from app.tasks.cleanup_tasks import (
    cleanup_expired_enrichment_data,
    cleanup_rate_limit_entries,
    cleanup_analytics_cache,
)

__all__ = [
    "celery_app",
    # Enrichment tasks
    "enrich_user_task",
    "queue_event_enrichments",
    "retry_failed_enrichments",
    # Cleanup tasks
    "cleanup_expired_enrichment_data",
    "cleanup_rate_limit_entries",
    "cleanup_analytics_cache",
]
