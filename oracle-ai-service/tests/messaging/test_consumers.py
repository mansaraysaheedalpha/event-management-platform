from unittest.mock import patch, MagicMock
from app.messaging import consumers
from app.schemas.messaging import ChatMessagePayload, SentimentScorePredictionPayload
from datetime import datetime, timezone


# We patch the Kafka classes and the analysis service at the module level
@patch("app.messaging.consumers.create_producer")
@patch("app.messaging.consumers.KafkaConsumer")
@patch("app.messaging.consumers.analysis_service")
def test_listen_for_chat_messages(
    mock_analysis_service, mock_kafka_consumer, mock_create_producer
):
    """
    Tests the full "consume -> process -> produce" loop for chat messages.
    """
    # 1. Setup
    # Create a fake incoming Kafka message
    chat_payload = ChatMessagePayload(
        messageId="msg_123",
        eventId="evt_1",
        userId="user_1",
        text="This is a great talk!",
        timestamp=datetime.now(timezone.utc),
    )
    fake_kafka_message = MagicMock()
    fake_kafka_message.value = chat_payload.model_dump(mode="json")

    # Configure the mock consumer to return our fake message once, then stop
    mock_kafka_consumer.return_value = [fake_kafka_message]

    # Configure the mock analysis service to return a predictable prediction
    sentiment_prediction = SentimentScorePredictionPayload(
        sourceMessageId="msg_123",
        eventId="evt_1",
        sentiment="positive",
        score=0.99,
        confidence=0.98,
        timestamp=datetime.now(timezone.utc),
    )
    mock_analysis_service.analyze_single_message.return_value = sentiment_prediction

    # Get a reference to the mock producer that will be created
    mock_producer = mock_create_producer.return_value

    # 2. Execute
    # We call the function that contains the consumer loop
    consumers.listen_for_chat_messages()

    # 3. Assert
    # Assert that the message was passed to the analysis service
    mock_analysis_service.analyze_single_message.assert_called_once_with(chat_payload)

    # Assert that the prediction result was published to the correct output topic
    mock_producer.send.assert_called_once_with(
        consumers.TOPIC_SENTIMENT_PREDICTIONS,
        value=sentiment_prediction.model_dump(mode="json"),
    )
