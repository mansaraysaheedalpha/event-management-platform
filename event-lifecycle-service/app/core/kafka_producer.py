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
    """
    producer = None
    try:
        producer = KafkaProducer(
            bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS,
            value_serializer=lambda v: json.dumps(v, default=str).encode("utf-8"),
            # You can add a timeout to catch connection issues faster during a request
            request_timeout_ms=5000,
        )
    except (NoBrokersAvailable, Exception) as e:
        logger.warning(f"Kafka producer unavailable: {e}. GraphQL will work without Kafka.")
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
