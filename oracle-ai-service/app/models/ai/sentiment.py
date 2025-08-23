# app/models/ai/sentiment.py

import json

# NOTE: TRANSFORMERS IS NO LONGER IMPORTED AT THE TOP LEVEL
from fastapi import HTTPException
from app.core.config import settings
from app.db.redis import redis_client


class SentimentModel:
    """
    The definitive, world-class version of the model manager.
    It uses LAZY LOADING and DEFERRED IMPORTS to guarantee instant startup.
    """

    def __init__(self, model_name: str):
        self.model_name = model_name
        self._model_pipeline = None

    @property
    def pipeline(self):
        """A property that lazily loads the model on its first access."""
        if self._model_pipeline is None:
            # --- DEFERRED IMPORT ---
            # The library is imported here, at the last possible moment.
            from transformers import pipeline

            print(f"First use detected. Lazily loading model: {self.model_name}...")
            try:
                self._model_pipeline = pipeline(
                    "sentiment-analysis", model=self.model_name
                )
                print("Sentiment analysis model loaded successfully.")
            except Exception as e:
                raise RuntimeError(f"Could not load sentiment model: {e}") from e
        return self._model_pipeline

    def predict(self, text: str) -> dict:
        """Analyzes sentiment using the lazily-loaded model."""
        if not text or not text.strip():
            return {"label": "neutral", "score": 0.0}

        cache_key = f"sentiment:{self.model_name}:{text}"
        try:
            cached_result = redis_client.get(cache_key)
            if cached_result:
                return json.loads(cached_result)
        except Exception as e:
            print(f"WARNING: Redis cache GET failed: {e}. Proceeding without cache.")

        try:
            result = self.pipeline(text, truncation=True)[0]
            formatted_result = {
                "label": result["label"].lower(),
                "score": round(result["score"], 4),
            }
            try:
                redis_client.set(cache_key, json.dumps(formatted_result), ex=86400)
            except Exception as e:
                print(f"WARNING: Redis cache SET failed: {e}.")
            return formatted_result
        except Exception as e:
            raise HTTPException(status_code=500, detail="AI model prediction failed.")


sentiment_model = SentimentModel(model_name=settings.SENTIMENT_MODEL_NAME)
