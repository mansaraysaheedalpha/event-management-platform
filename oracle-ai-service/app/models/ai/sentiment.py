from transformers import pipeline, Pipeline
from app.db.redis import redis_client
import json

class SentimentModel:
    """
     A wrapper class for the Hugging Face sentiment analysis pipeline
    that includes a caching layer to improve performance.
    """

    _model_pipeline: Pipeline = None

    @classmethod
    def get_pipeline(cls) -> Pipeline:
        """
        Initializes and returns the sentiment analysis pipeline.
        This is a private method that ensures the model is loaded only once.
        """
        if cls._model_pipeline is None:
            # This line downloads and caches a pre-trained sentiment analysis model.
            # This is a lightweight general-purpose sentiment model trained on SST-2 (movie reviews),
            # suitable for binary sentiment tasks like POSITIVE / NEGATIVE.

            cls._model_pipeline = pipeline(
                "sentiment-analysis",
                model="distilbert-base-uncased-finetuned-sst-2-english",
            )
        return cls._model_pipeline

    @classmethod
    def predict(cls, text: str) -> dict:
        """
        Analyzes the sentiment of a given text, using a cache to
        avoid re-computing results for the same text.
        """
        # --- CACHING LOGIC ---
        cache_key = f"sentiment:{text}"
        cached_result = redis_client.get(cache_key)

        if cached_result:
            return json.loads(cached_result)
        pipe = cls.get_pipeline()
        result = pipe(text)[0]

        # Format the result
        formatted_result = {
            "label": result["label"].lower(),
            "score": round(result["score"], 4),
        }

        # --- CACHING LOGIC ---
        # Store the new result in the cache for next time.
        # We'll set it to expire in 24 hours (86400 seconds).
        redis_client.set(cache_key, json.dumps(formatted_result), ex=86400)
    

        return formatted_result


sentiment_model = SentimentModel()
