from celery import Celery
from app.core.config import settings

# Initialize Celery
celery_app = Celery("worker", broker=settings.REDIS_URL, backend=settings.REDIS_URL)

# Tell Celery where to find our tasks
celery_app.conf.imports = ("app.tasks",)
