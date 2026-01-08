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
