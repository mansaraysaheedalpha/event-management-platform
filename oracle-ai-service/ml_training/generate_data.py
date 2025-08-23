# ml_training/generate_data.py

import pandas as pd
import numpy as np


def generate_attendance_data(num_samples=500):
    """
    Generates a synthetic dataset for training an attendance forecast model.
    """
    # Base features
    days_until_event = np.random.randint(1, 90, size=num_samples)
    marketing_spend = np.random.uniform(500, 10000, size=num_samples)
    current_registrations = np.random.randint(10, 500, size=num_samples)

    # Target variable (final_attendance) is a function of the features + some noise
    noise = np.random.normal(0, 50, size=num_samples)

    # The "secret formula" our model will try to learn:
    final_attendance = (
        50  # Base attendance
        + (current_registrations * 1.8)  # Strong correlation
        + (marketing_spend * 0.05)  # Weaker correlation
        - (
            days_until_event * 2
        )  # Negative correlation (more days = fewer signups so far)
        + noise
    )

    # Ensure attendance is a whole number and not negative
    final_attendance = np.maximum(0, final_attendance).astype(int)

    # Create a Pandas DataFrame
    df = pd.DataFrame(
        {
            "days_until_event": days_until_event,
            "marketing_spend": marketing_spend,
            "current_registrations": current_registrations,
            "final_attendance": final_attendance,
        }
    )

    # Save to a CSV file
    file_path = "ml_training/attendance_data.csv"
    df.to_csv(file_path, index=False)
    print(f"Successfully generated synthetic data at: {file_path}")
    return file_path


if __name__ == "__main__":
    generate_attendance_data()
