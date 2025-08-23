# ml_training/train_model.py

import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_squared_error
import joblib


def train_attendance_model(data_path="ml_training/attendance_data.csv"):
    """
    Loads data, trains a model, and serializes it to a file.
    """
    # 1. Load Data
    df = pd.read_csv(data_path)

    # 2. Define Features (X) and Target (y)
    features = ["current_registrations", "days_until_event", "marketing_spend"]
    target = "final_attendance"

    X = df[features]
    y = df[target]

    # 3. Split Data into Training and Testing sets
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42
    )

    # 4. Train the Model
    model = LinearRegression()
    model.fit(X_train, y_train)

    # 5. Evaluate the Model (optional, but good practice)
    predictions = model.predict(X_test)
    mse = mean_squared_error(y_test, predictions)
    print(f"Model training complete. Mean Squared Error: {mse:.2f}")

    # 6. Serialize and Save the Model
    model_path = "app/models/ml/production_models/attendance_model.joblib"
    joblib.dump(model, model_path)
    print(f"Model successfully saved to: {model_path}")
    return model_path


if __name__ == "__main__":
    train_attendance_model()
