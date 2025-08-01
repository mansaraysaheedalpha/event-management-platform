from app.schemas.analytics import AttendanceForecastRequest, AttendanceForecastResponse


def forecast_attendance(
    request: AttendanceForecastRequest,
) -> AttendanceForecastResponse:
    """
    This service function contains the business logic for forecasting attendance.
    In a real system, this is where you would load a trained ML model
    (e.g., from TensorFlow, PyTorch, or scikit-learn) and use it to generate a prediction.

    For now, we return a hardcoded, realistic response.
    """

    # Simulate a prediction based on the input
    predicted_attendance = request.current_registrations * 2 + 50

    return AttendanceForecastResponse(
        predicted_final_attendance=int(predicted_attendance),
        confidence_interval={
            "lower_bound": int(predicted_attendance * 0.8),
            "upper_bound": int(predicted_attendance * 1.2),
        },
        growth_trajectory=[],
        factors_influencing=[],
    )
