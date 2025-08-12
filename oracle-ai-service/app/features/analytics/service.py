import random
from app.features.analytics.schemas import (
    AttendanceForecastRequest,
    AttendanceForecastResponse,
    ROICalculationRequest,
    ROICalculationResponse,
    EventTimingRequest,
    EventTimingResponse,
    SuccessProbabilityRequest,
    SuccessProbabilityResponse,
    EngagementPredictionRequest,
    EngagementPredictionResponse,
)


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


def calculate_roi(request: ROICalculationRequest) -> ROICalculationResponse:
    """
    Simulates the calculation of event ROI.
    """
    # Simple financial simulation
    predicted_revenue = (
        request.current_registrations + 50
    ) * request.ticket_price  # Assume 50 more registrations
    profit_projection = predicted_revenue - request.total_costs
    predicted_roi = (
        (profit_projection / request.total_costs) if request.total_costs > 0 else 0
    )
    break_even_attendees = (
        request.total_costs / request.ticket_price if request.ticket_price > 0 else 0
    )

    return ROICalculationResponse(
        predicted_roi=round(predicted_roi, 2),
        break_even_point_attendees=int(break_even_attendees),
        profit_projection=profit_projection,
    )


def get_optimal_timing(request: EventTimingRequest) -> EventTimingResponse:
    """Simulates predicting the best time to schedule an event."""
    return EventTimingResponse(
        optimal_date=date(2026, 10, 26),
        optimal_time=time(14, 0, 0),
        confidence_score=round(random.uniform(0.75, 0.95), 2),
    )


def get_success_probability(
    request: SuccessProbabilityRequest,
) -> SuccessProbabilityResponse:
    """Simulates calculating the probability of an event's success."""
    # Simple weighted average for simulation
    prob = (
        (request.registration_rate * 0.4)
        + (request.speaker_quality_score * 0.4)
        + (request.marketing_reach * 0.2 / 10000)
    )
    prob = min(1.0, max(0.0, round(prob, 2)))  # Ensure it's a valid probability

    return SuccessProbabilityResponse(
        success_probability=prob,
        success_factors=["High speaker quality score", "Strong initial registration"],
        risk_factors=["High market competition"],
    )


def predict_engagement(
    request: EngagementPredictionRequest,
) -> EngagementPredictionResponse:
    """Simulates predicting engagement for various sessions."""
    predictions = []
    for i, session in enumerate(request.sessions):
        predictions.append(
            EngagementPredictionResponse.SessionPrediction(
                session_id=session.session_id,
                engagement_score=round(random.uniform(60.0, 95.0), 2),
                popularity_rank=i + 1,
            )
        )
    # Sort by score to make the rank meaningful
    predictions.sort(key=lambda x: x.engagement_score, reverse=True)
    for i, p in enumerate(predictions):
        p.popularity_rank = i + 1

    return EngagementPredictionResponse(session_predictions=predictions)
