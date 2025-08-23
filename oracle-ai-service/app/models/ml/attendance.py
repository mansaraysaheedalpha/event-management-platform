# app/models/ml/attendance.py

import numpy as np
import joblib
from typing import List


class AttendanceModelManager:
    """
    A world-class model manager that loads a REAL, serialized model from a file.
    """

    def __init__(self, model_path: str):
        self.model_path = model_path
        self._model = None  # Lazy-loaded

    @property
    def model(self):
        """A property that lazily loads the real model on its first access."""
        if self._model is None:
            print(f"Lazily loading REAL attendance model from: {self.model_path}")
            try:
                self._model = joblib.load(self.model_path)
                print("Real attendance model loaded successfully.")
            except FileNotFoundError:
                print(f"CRITICAL: Model file not found at {self.model_path}")
                raise
            except Exception as e:
                print(f"CRITICAL: Failed to load model. Error: {e}")
                raise
        return self._model

    def predict(
        self, current_registrations: int, days_until_event: int, marketing_spend: float
    ) -> np.ndarray:
        """Prepares features and gets a prediction from the loaded model."""
        # The model expects a 2D array with features in a specific order.
        features = np.array(
            [[current_registrations, days_until_event, marketing_spend]]
        )
        return self.model.predict(features)


# This now points to our real, trained model file.
attendance_model = AttendanceModelManager(
    model_path="app/models/ml/production_models/attendance_model.joblib"
)
