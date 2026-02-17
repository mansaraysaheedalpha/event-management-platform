#app/workers.py
from celery import Celery
from app.core.config import settings

def get_celery_broker_url():
    """
    Get the broker URL with SSL configuration for Upstash Redis.
    Upstash uses rediss:// (TLS) which requires ssl_cert_reqs parameter for Celery.
    """
    url = settings.REDIS_URL
    if url and url.startswith("rediss://"):
        # Add SSL cert requirements for TLS connections
        separator = "&" if "?" in url else "?"
        url = f"{url}{separator}ssl_cert_reqs=CERT_REQUIRED"
    return url

# Get the configured broker URL with SSL settings
broker_url = get_celery_broker_url()

# Initialize Celery
celery_app = Celery("worker", broker=broker_url, backend=broker_url)

# Tell Celery where to find our tasks
celery_app.conf.imports = ("app.tasks",)

# Celery Beat schedule for periodic tasks
celery_app.conf.beat_schedule = {
    "process-rfp-deadlines": {
        "task": "app.tasks.process_rfp_deadlines",
        "schedule": 300.0,  # Every 5 minutes
    },
    "send-rfp-deadline-reminders": {
        "task": "app.tasks.send_rfp_deadline_reminders",
        "schedule": 3600.0,  # Every hour
    },
    "refresh-exchange-rates": {
        "task": "app.tasks.refresh_exchange_rates",
        "schedule": 86400.0,  # Daily (24 hours)
    },
}
