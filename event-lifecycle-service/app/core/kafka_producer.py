# app/core/kafka_producer.py

import json
from kafka import KafkaProducer
from app.core.config import settings


def get_kafka_producer():
    """
    FastAPI dependency to create and yield a Kafka producer.
    Ensures the producer is properly closed after the request.
    """
    producer = KafkaProducer(
        bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS,
        value_serializer=lambda v: json.dumps(v, default=str).encode("utf-8"),
        # You can add a timeout to catch connection issues faster during a request
        request_timeout_ms=5000,
    )
    try:
        yield producer
    finally:
        producer.flush()  # Ensure all buffered messages are sent
        producer.close()
