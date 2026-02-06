# app/tasks/celery_app.py
"""
Celery application configuration.

Provides background task processing with:
- Rate limiting per task
- Retry with exponential backoff
- Task routing and priorities
"""

from celery import Celery

from app.core.config import settings


def _ensure_ssl_params(url: str) -> str:
    """Append ssl_cert_reqs for rediss:// URLs (required by Celery)."""
    if url and url.startswith("rediss://") and "ssl_cert_reqs" not in url:
        separator = "&" if "?" in url else "?"
        return f"{url}{separator}ssl_cert_reqs=CERT_NONE"
    return url


broker_url = _ensure_ssl_params(settings.CELERY_BROKER_URL)
backend_url = _ensure_ssl_params(settings.CELERY_RESULT_BACKEND)

# Create Celery app
celery_app = Celery(
    "oracle_tasks",
    broker=broker_url,
    backend=backend_url,
)

# Configure Celery
celery_app.conf.update(
    # Task settings
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,

    # Task execution
    task_acks_late=True,  # Acknowledge after task completes
    task_reject_on_worker_lost=True,  # Requeue if worker dies

    # Rate limiting
    worker_prefetch_multiplier=1,  # Prevent worker from grabbing too many tasks

    # Result backend
    result_expires=3600,  # Results expire after 1 hour

    # Retry settings
    task_default_retry_delay=60,  # 1 minute default retry delay

    # Task routing
    task_routes={
        "app.tasks.enrichment_tasks.*": {"queue": "enrichment"},
        "app.tasks.analytics_tasks.*": {"queue": "analytics"},
    },

    # Priority queues (higher number = lower priority)
    task_queue_max_priority=10,
    task_default_priority=5,
)

# Autodiscover tasks
celery_app.autodiscover_tasks(["app.tasks"])
