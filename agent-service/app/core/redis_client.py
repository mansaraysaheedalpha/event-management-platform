import redis.asyncio as redis
from typing import Optional, List, Dict, Any, Tuple
import logging
import json

logger = logging.getLogger(__name__)


class RedisClient:
    """Redis client for Pub/Sub, Streams, and state management"""

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
        """Subscribe to Pub/Sub channels"""
        self._pubsub = self._client.pubsub()
        await self._pubsub.subscribe(*channels)
        return self._pubsub

    async def publish(self, channel: str, message: str):
        """Publish message to Pub/Sub channel"""
        await self._client.publish(channel, message)

    # ==================== Redis Streams Methods ====================

    async def create_consumer_group(
        self,
        stream: str,
        group: str,
        start_id: str = "0"
    ) -> bool:
        """
        Create a consumer group for a stream.
        Returns True if created, False if already exists.
        """
        try:
            await self._client.xgroup_create(
                stream,
                group,
                id=start_id,
                mkstream=True  # Create stream if it doesn't exist
            )
            logger.info(f"Created consumer group '{group}' for stream '{stream}'")
            return True
        except redis.ResponseError as e:
            if "BUSYGROUP" in str(e):
                # Group already exists
                logger.debug(f"Consumer group '{group}' already exists for stream '{stream}'")
                return False
            raise

    async def xread_streams(
        self,
        streams: Dict[str, str],
        count: int = 100,
        block: int = 1000
    ) -> List[Tuple[str, List[Tuple[str, Dict[str, str]]]]]:
        """
        Read from multiple streams (without consumer groups).

        Args:
            streams: Dict mapping stream names to last IDs (use '$' for new messages only)
            count: Max number of messages per stream
            block: Block time in milliseconds (0 = no block)

        Returns:
            List of (stream_name, [(message_id, {field: value}), ...])
        """
        try:
            result = await self._client.xread(
                streams=streams,
                count=count,
                block=block
            )
            return result or []
        except Exception as e:
            logger.error(f"Error reading from streams: {e}")
            return []

    async def xreadgroup_streams(
        self,
        group: str,
        consumer: str,
        streams: Dict[str, str],
        count: int = 100,
        block: int = 1000
    ) -> List[Tuple[str, List[Tuple[str, Dict[str, str]]]]]:
        """
        Read from streams using consumer groups (reliable delivery).

        Args:
            group: Consumer group name
            consumer: Consumer name within the group
            streams: Dict mapping stream names to IDs (use '>' for new messages)
            count: Max number of messages
            block: Block time in milliseconds

        Returns:
            List of (stream_name, [(message_id, {field: value}), ...])
        """
        try:
            result = await self._client.xreadgroup(
                groupname=group,
                consumername=consumer,
                streams=streams,
                count=count,
                block=block
            )
            return result or []
        except Exception as e:
            logger.error(f"Error reading from consumer group: {e}")
            return []

    async def xack(self, stream: str, group: str, *message_ids: str) -> int:
        """Acknowledge messages in a consumer group"""
        try:
            return await self._client.xack(stream, group, *message_ids)
        except Exception as e:
            logger.error(f"Error acknowledging messages: {e}")
            return 0

    def parse_stream_message(self, data: Dict[str, str]) -> Optional[Dict[str, Any]]:
        """
        Parse a stream message's data field (JSON encoded).

        Args:
            data: Raw message data from stream

        Returns:
            Parsed JSON object or None if parsing fails
        """
        try:
            if 'data' in data:
                return json.loads(data['data'])
            return data
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse stream message: {e}")
            return None


# Global instance (will be initialized with settings in main.py)
redis_client: Optional[RedisClient] = None
