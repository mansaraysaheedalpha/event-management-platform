# app/models/ml/churn.py

import numpy as np
from typing import List, Dict, Any


class MockChurnModel:
    """
    Simulates a pre-trained binary classification model (e.g., Logistic Regression).
    """

    def predict_proba(self, features: np.ndarray) -> np.ndarray:
        """
        Predicts the probability of churn.
        Returns probabilities for two classes: [prob_not_churn, prob_churn].
        """
        probabilities = []
        for feature_set in features:
            sessions = feature_set[0]
            chats = feature_set[1]

            # Heuristic: Lower engagement metrics lead to a higher churn probability.
            engagement_score = (sessions * 2) + chats
            # A simple sigmoid-like transformation to get a probability
            prob_churn = 1 / (1 + np.exp(0.5 * engagement_score - 2))

            probabilities.append([1 - prob_churn, prob_churn])

        return np.array(probabilities)


class ChurnModelManager:
    """
    A world-class model manager for the churn classifier, using our
    proven lazy-loading pattern.
    """

    def __init__(self):
        self._model: MockChurnModel | None = None

    @property
    def model(self) -> MockChurnModel:
        if self._model is None:
            print("Lazily loading churn prediction model...")
            self._model = MockChurnModel()
            print("Churn prediction model loaded.")
        return self._model

    def predict_proba(self, attendee_data: List[Dict[str, Any]]) -> np.ndarray:
        """Prepares features and gets churn probabilities from the model."""
        # Convert the list of Pydantic models into a NumPy array for the model
        features = np.array(
            [
                [data.sessions_attended, data.chat_messages_sent]
                for data in attendee_data
            ]
        )
        return self.model.predict_proba(features)


# Create a single, reusable instance
churn_model = ChurnModelManager()
