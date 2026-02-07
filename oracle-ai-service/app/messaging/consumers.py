#app/messaging/consumers.py
import asyncio
import json
import threading
from kafka import KafkaConsumer, KafkaProducer
from pydantic import ValidationError
from app.core.config import settings
from app.schemas.messaging import *
from app.features.analysis import service as analysis_service
from . import service

# Define Kafka topics
TOPIC_CHAT_MESSAGES = "platform.events.chat.message.v1"
TOPIC_USER_INTERACTIONS = "real-time.user.interactions"
TOPIC_ATTENDANCE_DATA = "real-time.attendance.data"
TOPIC_SESSION_FEEDBACK = "real-time.session.feedback"
TOPIC_NETWORK_CONNECTIONS = "real-time.network.connections"

TOPIC_SENTIMENT_PREDICTIONS = "oracle.predictions.sentiment.v1"
TOPIC_ENGAGEMENT_PREDICTIONS = "oracle.predictions.engagement-predictions"
TOPIC_CAPACITY_FORECASTS = "oracle.predictions.capacity-forecasts"
TOPIC_NETWORKING_SUGGESTIONS = "oracle.predictions.networking-suggestions"
TOPIC_SUCCESS_INSIGHTS = "oracle.predictions.success-insights"


def get_kafka_config():
    """Get Kafka configuration with SASL authentication if configured."""
    config = {
        'bootstrap_servers': settings.KAFKA_BOOTSTRAP_SERVERS,
    }

    # Add SASL authentication for Confluent Cloud
    if settings.KAFKA_API_KEY and settings.KAFKA_API_SECRET:
        config.update({
            'security_protocol': settings.KAFKA_SECURITY_PROTOCOL,
            'sasl_mechanism': settings.KAFKA_SASL_MECHANISM,
            'sasl_plain_username': settings.KAFKA_API_KEY,
            'sasl_plain_password': settings.KAFKA_API_SECRET,
        })

    return config


def create_producer():
    """Creates a Kafka producer instance with authentication."""
    config = get_kafka_config()
    config['value_serializer'] = lambda v: json.dumps(v, default=str).encode("utf-8")
    return KafkaProducer(**config)


def listen_for_chat_messages():
    """Listens for chat messages, analyzes them, and publishes sentiment."""
    config = get_kafka_config()
    config['value_deserializer'] = lambda v: json.loads(v.decode("utf-8"))
    consumer = KafkaConsumer(TOPIC_CHAT_MESSAGES, **config)
    producer = create_producer()
    print(f"--> Consumer started for topic: {TOPIC_CHAT_MESSAGES}")
    for message in consumer:
        try:
            chat_data = ChatMessagePayload(**message.value)
            sentiment_prediction = analysis_service.analyze_single_message(chat_data)
            producer.send(
                TOPIC_SENTIMENT_PREDICTIONS,
                value=sentiment_prediction.model_dump(mode="json"),
            )
            print(f"    Published sentiment for message: {chat_data.messageId}")
        except ValidationError as e:
            print(f"ERROR on {TOPIC_CHAT_MESSAGES}: Malformed message - {e}")


def listen_for_interactions():
    """Listens for user interactions and publishes engagement predictions."""
    config = get_kafka_config()
    config['value_deserializer'] = lambda v: json.loads(v.decode("utf-8"))
    consumer = KafkaConsumer(TOPIC_USER_INTERACTIONS, **config)
    producer = create_producer()
    print(f"--> Consumer started for topic: {TOPIC_USER_INTERACTIONS}")
    for message in consumer:
        try:
            interaction_data = UserInteractionPayload(**message.value)
            prediction = service.process_user_interaction(interaction_data)
            producer.send(
                TOPIC_ENGAGEMENT_PREDICTIONS, value=prediction.model_dump(mode="json")
            )
            print(
                f"    Published engagement for interaction: {interaction_data.interactionId}"
            )
        except ValidationError as e:
            print(f"ERROR on {TOPIC_USER_INTERACTIONS}: Malformed message - {e}")


def listen_for_attendance():
    """Listens for attendance data and publishes capacity forecasts."""
    config = get_kafka_config()
    config['value_deserializer'] = lambda v: json.loads(v.decode("utf-8"))
    consumer = KafkaConsumer(TOPIC_ATTENDANCE_DATA, **config)
    producer = create_producer()
    print(f"--> Consumer started for topic: {TOPIC_ATTENDANCE_DATA}")
    for message in consumer:
        try:
            attendance_data = AttendanceUpdatePayload(**message.value)
            prediction = service.process_attendance_update(attendance_data)
            producer.send(
                TOPIC_CAPACITY_FORECASTS, value=prediction.model_dump(mode="json")
            )
            print(
                f"    Published capacity forecast for session: {attendance_data.sessionId}"
            )
        except ValidationError as e:
            print(f"ERROR on {TOPIC_ATTENDANCE_DATA}: Malformed message - {e}")


def listen_for_feedback():
    """Listens for session feedback and publishes success insights."""
    config = get_kafka_config()
    config['value_deserializer'] = lambda v: json.loads(v.decode("utf-8"))
    consumer = KafkaConsumer(TOPIC_SESSION_FEEDBACK, **config)
    producer = create_producer()
    print(f"--> Consumer started for topic: {TOPIC_SESSION_FEEDBACK}")
    for message in consumer:
        try:
            feedback_data = SessionFeedbackPayload(**message.value)
            prediction = service.process_session_feedback(feedback_data)
            producer.send(
                TOPIC_SUCCESS_INSIGHTS, value=prediction.model_dump(mode="json")
            )
            print(
                f"    Published success insight for session: {feedback_data.sessionId}"
            )
        except ValidationError as e:
            print(f"ERROR on {TOPIC_SESSION_FEEDBACK}: Malformed message - {e}")


def listen_for_connections():
    """Listens for new network connections and publishes new suggestions."""
    config = get_kafka_config()
    config['value_deserializer'] = lambda v: json.loads(v.decode("utf-8"))
    consumer = KafkaConsumer(TOPIC_NETWORK_CONNECTIONS, **config)
    producer = create_producer()
    print(f"--> Consumer started for topic: {TOPIC_NETWORK_CONNECTIONS}")

    for message in consumer:
        try:
            connection_data = NetworkConnectionPayload(**message.value)
            # Process connection asynchronously (uses AI matchmaking)
            # Use asyncio.run() which creates a fresh event loop for each message
            prediction = asyncio.run(service.process_network_connection(connection_data))

            # Only publish if we have a real suggestion (non-empty suggestedUserId)
            if prediction.suggestedUserId:
                producer.send(
                    TOPIC_NETWORKING_SUGGESTIONS, value=prediction.model_dump(mode="json")
                )
                print(
                    f"    Published networking suggestion for user: {connection_data.user1_id}"
                )
            else:
                print(
                    f"    Skipped suggestion for user {connection_data.user1_id} (no candidates)"
                )
        except ValidationError as e:
            print(f"ERROR on {TOPIC_NETWORK_CONNECTIONS}: Malformed message - {e}")
        except Exception as e:
            print(f"ERROR on {TOPIC_NETWORK_CONNECTIONS}: Processing failed - {e}")


def run_all_consumers():
    """Runs all consumer listeners in separate threads."""
    threads = [
        threading.Thread(target=listen_for_chat_messages),
        threading.Thread(target=listen_for_interactions),
        threading.Thread(target=listen_for_attendance),
        threading.Thread(target=listen_for_feedback),
        threading.Thread(target=listen_for_connections),
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
