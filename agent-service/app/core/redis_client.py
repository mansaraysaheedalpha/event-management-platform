import redis.asyncio as redis
from typing import Optional
import logging

logger = logging.getLogger(__name__)


class RedisClient:
    """Redis client for Pub/Sub and state management"""

    def __init__(self, url: str = "redis://localhost:6379"):
        self.url = url
        self._client: Optional[redis.Redis] = None
        self._pubsub: Optional[redis.client.PubSub] = None

    async def connect(self):
        """Connect to Redis"""
        try:
            self._client = await redis.from_url(
                self.url,
                encoding="utf-8",
                decode_responses=True
            )
            await self._client.ping()
            logger.info("✅ Connected to Redis")
        except Exception as e:
            logger.error(f"❌ Failed to connect to Redis: {e}")
            raise

    async def disconnect(self):
        """Disconnect from Redis"""
        if self._client:
            await self._client.aclose()
            logger.info("Disconnected from Redis")

    @property
    def client(self) -> redis.Redis:
        """Get Redis client"""
        if not self._client:
            raise RuntimeError("Redis client not connected. Call connect() first.")
        return self._client

    async def subscribe(self, *channels: str):
        """Subscribe to channels"""
        self._pubsub = self._client.pubsub()
        await self._pubsub.subscribe(*channels)
        return self._pubsub

    async def publish(self, channel: str, message: str):
        """Publish message to channel"""
        await self._client.publish(channel, message)


# Global instance (will be initialized with settings in main.py)
redis_client: Optional[RedisClient] = None
