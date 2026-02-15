import redis.asyncio as redis
from typing import Optional, List, Dict, Any, Tuple
import logging
import json

from app.core.circuit_breaker import (
    redis_circuit_breaker,
    CircuitBreakerError,
    CircuitState
)

logger = logging.getLogger(__name__)


class RedisClient:
    """Redis client for Pub/Sub, Streams, and state management with circuit breaker protection"""

    def __init__(self, url: str = "redis://localhost:6379"):
        self.url = url
        self._client: Optional[redis.Redis] = None
        self._pubsub: Optional[redis.client.PubSub] = None
        self._circuit_breaker = redis_circuit_breaker

    @property
    def circuit_state(self) -> CircuitState:
        """Get current circuit breaker state"""
        return self._circuit_breaker.state

    @property
    def circuit_breaker_stats(self) -> Dict:
        """Get circuit breaker statistics"""
        return self._circuit_breaker.stats.to_dict()

    async def connect(self):
        """Connect to Redis"""
        try:
            self._client = await redis.from_url(
                self.url,
                encoding="utf-8",
                decode_responses=True
            )
            await self._client.ping()
            # Reset circuit breaker on successful connection
            self._circuit_breaker.reset()
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
        """Subscribe to Pub/Sub channels with circuit breaker protection"""
        async with self._circuit_breaker:
            self._pubsub = self._client.pubsub()
            await self._pubsub.subscribe(*channels)
            return self._pubsub

    async def publish(self, channel: str, message: str):
        """Publish message to Pub/Sub channel with circuit breaker protection"""
        async with self._circuit_breaker:
            await self._client.publish(channel, message)

    # ==================== Redis Streams Methods ====================

    async def create_consumer_group(
        self,
        stream: str,
        group: str,
        start_id: str = "0"
    ) -> bool:
        """
        Create a consumer group for a stream with circuit breaker protection.
        Returns True if created, False if already exists.
        """
        try:
            async with self._circuit_breaker:
                try:
                    await self._client.xgroup_create(
                        stream,
                        group,
                        id=start_id,
                        mkstream=True  # Create stream if it doesn't exist
                    )
                except redis.ResponseError as e:
                    if "BUSYGROUP" in str(e):
                        # Group already exists — handle INSIDE the circuit breaker context
                        # so __aexit__ sees no exception and records a success, not a failure
                        logger.debug(f"Consumer group '{group}' already exists for stream '{stream}'")
                        return False
                    raise
            logger.info(f"Created consumer group '{group}' for stream '{stream}'")
            return True
        except CircuitBreakerError as e:
            logger.warning(f"Circuit breaker open for create_consumer_group: {e}")
            raise

    async def xread_streams(
        self,
        streams: Dict[str, str],
        count: int = 100,
        block: int = 1000
    ) -> List[Tuple[str, List[Tuple[str, Dict[str, str]]]]]:
        """
        Read from multiple streams (without consumer groups) with circuit breaker protection.

        Args:
            streams: Dict mapping stream names to last IDs (use '$' for new messages only)
            count: Max number of messages per stream
            block: Block time in milliseconds (0 = no block)

        Returns:
            List of (stream_name, [(message_id, {field: value}), ...])
        """
        try:
            async with self._circuit_breaker:
                result = await self._client.xread(
                    streams=streams,
                    count=count,
                    block=block
                )
                return result or []
        except CircuitBreakerError as e:
            logger.warning(f"Circuit breaker open for xread_streams: {e}")
            return []
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
        Read from streams using consumer groups (reliable delivery) with circuit breaker protection.

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
            async with self._circuit_breaker:
                result = await self._client.xreadgroup(
                    groupname=group,
                    consumername=consumer,
                    streams=streams,
                    count=count,
                    block=block
                )
                return result or []
        except CircuitBreakerError as e:
            logger.warning(f"Circuit breaker open for xreadgroup_streams: {e}")
            return []
        except Exception as e:
            logger.error(f"Error reading from consumer group: {e}")
            return []

    async def xack(self, stream: str, group: str, *message_ids: str) -> int:
        """
        Acknowledge messages in a consumer group with circuit breaker protection.

        IMPORTANT: If circuit breaker is open, returns 0 and messages will NOT be
        acknowledged. This means messages will be redelivered when circuit recovers
        (at-least-once semantics). Ensure your message handlers are idempotent.

        Args:
            stream: Stream name
            group: Consumer group name
            *message_ids: Message IDs to acknowledge

        Returns:
            Number of messages successfully acknowledged (0 if circuit open)
        """
        try:
            async with self._circuit_breaker:
                return await self._client.xack(stream, group, *message_ids)
        except CircuitBreakerError as e:
            # Messages will be redelivered when circuit recovers - at-least-once semantics
            logger.warning(
                f"Circuit breaker open for xack: {e}. "
                f"{len(message_ids)} message(s) will be redelivered when circuit recovers."
            )
            return 0
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
