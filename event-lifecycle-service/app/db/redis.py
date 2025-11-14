# app/db/redis.py
import redis
from app.core.config import settings


def get_redis_client():
    """
    Creates and returns a new Redis client instance.
    This is useful for creating fresh connections, like in a Celery task.
    """
    return redis.from_url(settings.REDIS_URL, decode_responses=True)


# This creates a single, shared instance that can be imported by other modules.
# This is what your crud_session.py file is looking for.
redis_client = get_redis_client()
