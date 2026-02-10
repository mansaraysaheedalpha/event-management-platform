# app/core/kafka_producer.py

import json
import logging
import threading
from kafka import KafkaProducer
from kafka.errors import NoBrokersAvailable
from app.core.config import settings

logger = logging.getLogger(__name__)

# Module-level singleton
_producer: KafkaProducer | None = None
_producer_lock = threading.Lock()
_initialized = False


def _create_producer() -> KafkaProducer | None:
    """Create a new KafkaProducer instance."""
    if not settings.KAFKA_BOOTSTRAP_SERVERS:
        logger.warning("Kafka bootstrap servers not configured. Kafka disabled.")
        return None

    try:
        kafka_config = {
            "bootstrap_servers": settings.KAFKA_BOOTSTRAP_SERVERS,
            "value_serializer": lambda v: json.dumps(v, default=str).encode("utf-8"),
            "request_timeout_ms": 10000,
            "api_version_auto_timeout_ms": 10000,
            "acks": "all",
            "retries": 3,
        }

        logger.info(f"Connecting to Kafka at: {settings.KAFKA_BOOTSTRAP_SERVERS[:30]}...")

        if settings.KAFKA_API_KEY and settings.KAFKA_API_SECRET:
            kafka_config.update({
                "security_protocol": settings.KAFKA_SECURITY_PROTOCOL or "SASL_SSL",
                "sasl_mechanism": settings.KAFKA_SASL_MECHANISM or "PLAIN",
                "sasl_plain_username": settings.KAFKA_API_KEY,
                "sasl_plain_password": settings.KAFKA_API_SECRET,
            })
            logger.info("Kafka configured with SASL_SSL authentication")

        producer = KafkaProducer(**kafka_config)
        logger.info("Kafka producer connected successfully")
        return producer

    except (NoBrokersAvailable, Exception) as e:
        logger.warning(f"Kafka producer unavailable: {e}. Service will work without Kafka.")
        return None


def get_kafka_singleton() -> KafkaProducer | None:
    """Get or create the singleton Kafka producer."""
    global _producer, _initialized
    if not _initialized:
        with _producer_lock:
            if not _initialized:
                _producer = _create_producer()
                _initialized = True
    return _producer


def get_kafka_producer():
    """FastAPI dependency that yields the singleton Kafka producer."""
    yield get_kafka_singleton()


def shutdown_kafka_producer():
    """Call during app shutdown to flush and close the producer."""
    global _producer, _initialized
    with _producer_lock:
        if _producer:
            try:
                _producer.flush()
                _producer.close()
                logger.info("Kafka producer shut down cleanly")
            except Exception as e:
                logger.error(f"Error closing Kafka producer: {e}")
            _producer = None
        _initialized = False