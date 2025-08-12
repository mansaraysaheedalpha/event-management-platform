#app/db/redis.py
import redis
from app.core.config import settings

# Create a reusable Redis client instance
redis_client = redis.from_url(settings.REDIS_URL, decode_responses=True)
