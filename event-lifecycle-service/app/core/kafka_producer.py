# app/core/kafka_producer.py

import json
import logging
from kafka import KafkaProducer
from kafka.errors import NoBrokersAvailable
from app.core.config import settings

logger = logging.getLogger(__name__)


def get_kafka_producer():
    """
    FastAPI dependency to create and yield a Kafka producer.
    Ensures the producer is properly closed after the request.
    Gracefully handles Kafka unavailability by returning None.

    Supports SASL_SSL authentication for Confluent Cloud.
    """
    producer = None

    # Skip if no Kafka bootstrap servers configured
    if not settings.KAFKA_BOOTSTRAP_SERVERS:
        logger.warning("Kafka bootstrap servers not configured. Kafka disabled.")
        yield None
        return

    try:
        # Base configuration
        kafka_config = {
            "bootstrap_servers": settings.KAFKA_BOOTSTRAP_SERVERS,
            "value_serializer": lambda v: json.dumps(v, default=str).encode("utf-8"),
            "request_timeout_ms": 10000,
            "api_version_auto_timeout_ms": 10000,
        }

        # Add SASL authentication if credentials are provided (for Confluent Cloud)
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

    except (NoBrokersAvailable, Exception) as e:
        logger.warning(f"Kafka producer unavailable: {e}. Service will work without Kafka.")
        producer = None

    try:
        yield producer
    finally:
        if producer:
            try:
                producer.flush()  # Ensure all buffered messages are sent
                producer.close()
            except Exception as e:
                logger.error(f"Error closing Kafka producer: {e}")
