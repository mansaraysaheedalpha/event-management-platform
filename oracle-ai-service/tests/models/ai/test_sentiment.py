# tests/models/ai/test_sentiment.py

import pytest
import json
from fastapi import HTTPException
from app.models.ai.sentiment import SentimentModel

mock_model_output_positive = [{"label": "POSITIVE", "score": 0.999}]


@pytest.fixture
def mock_redis(mocker):
    """A fixture to mock the redis client for tests using pytest-mock."""
    redis_cache = {}

    def mock_get(key):
        return redis_cache.get(key)

    def mock_set(key, value, ex):
        redis_cache[key] = value

    mocker.patch("app.models.ai.sentiment.redis_client.get", side_effect=mock_get)
    mocker.patch("app.models.ai.sentiment.redis_client.set", side_effect=mock_set)

    return redis_cache


def test_predict_correctly_uses_mocked_model(mocker, mock_redis):
    """
    Tests that a cache miss correctly calls the mocked model pipeline.
    """
    mock_pipeline_instance = mocker.MagicMock()
    mock_pipeline_instance.return_value = mock_model_output_positive

    mocker.patch(
        "app.models.ai.sentiment.SentimentModel.pipeline",
        new_callable=mocker.PropertyMock,
        return_value=mock_pipeline_instance,
    )

    model = SentimentModel(model_name="test-model-lazy")
    result = model.predict("This is a wonderful event!")

    assert result["label"] == "positive"
    assert result["score"] == 0.999
    mock_pipeline_instance.assert_called_once_with(
        "This is a wonderful event!", truncation=True
    )


def test_predict_with_cache_hit_never_accesses_model(mocker, mock_redis):
    """
    Tests that a cache hit NEVER accesses the model pipeline property.
    """
    mock_pipeline_prop = mocker.patch(
        "app.models.ai.sentiment.SentimentModel.pipeline",
        new_callable=mocker.PropertyMock,
    )

    text = "This event is amazing!"
    cached_value = '{"label": "positive", "score": 0.95}'
    cache_key = f"sentiment:test-model-lazy:{text}"
    mock_redis[cache_key] = cached_value

    model = SentimentModel(model_name="test-model-lazy")
    result = model.predict(text)

    assert result["label"] == "positive"
    assert result["score"] == 0.95
    mock_pipeline_prop.assert_not_called()
