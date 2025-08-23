# app/models/ml/engagement.py

from typing import List, Dict, Any


class EngagementModelManager:
    """
    A model manager for predicting session engagement.
    Includes a feature engineering step to score topics.
    """

    def __init__(self):
        # This simulates a pre-trained model and its associated assets.
        # In a real system, this keyword weighting could be learned from data.
        self.topic_weights = {
            "ai": 10,
            "machine learning": 10,
            "deep learning": 10,
            "microservices": 9,
            "cloud": 8,
            "kubernetes": 8,
            "docker": 8,
            "data": 7,
            "analytics": 7,
            "marketing": 5,
            "sales": 5,
        }
        self._model = None  # Lazy-loaded

    def _feature_engineer(self, topic: str) -> float:
        """
        A simple feature engineering function.
        It scores a topic based on the presence of weighted keywords.
        """
        score = 50.0  # Base score
        topic_lower = topic.lower()
        for keyword, weight in self.topic_weights.items():
            if keyword in topic_lower:
                score += weight * 5  # Amplify the weight
        return min(score, 100.0)  # Cap the score at 100

    def predict(self, sessions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Prepares features, gets predictions, and returns results."""
        predictions = []
        for session in sessions:
            # 1. Feature Engineering
            feature_score = self._feature_engineer(session.topic)

            # 2. Prediction (simulated model)
            # The "model" simply adds some noise to the engineered feature score.
            predicted_score = feature_score + (
                -5 + (10 * (hash(session.session_id) % 100) / 100)
            )

            predictions.append(
                {"session_id": session.session_id, "score": round(predicted_score, 2)}
            )
        return predictions


# Create a single, reusable instance for the application to use
engagement_model = EngagementModelManager()
