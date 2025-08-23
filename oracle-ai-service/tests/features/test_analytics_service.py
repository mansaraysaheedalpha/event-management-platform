# tests/features/test_analytics_service.py

import pytest
import numpy as np
from datetime import time
from app.features.analytics.service import *
from app.features.analytics.schemas import *


def test_forecast_attendance_uses_model_and_formats_response(mocker):
    """
    Tests that the forecast_attendance service correctly prepares data,
    calls the prediction model, and formats the output into the API response.
    """
    # 1. Arrange
    # The input data for the API request
    request = AttendanceForecastRequest(
        event_id="evt_123",
        current_registrations=250,
        days_until_event=30,
        marketing_spend=5000.0,
    )

    # Mock the prediction from our attendance model.
    # The model is expected to return a NumPy array.
    mock_prediction_value = 515.0
    mock_model = mocker.patch("app.features.analytics.service.attendance_model.predict")
    mock_model.return_value = np.array([mock_prediction_value])

    # 2. Act
    response = forecast_attendance(request)

    # 3. Assert
    # Assert that the model was called correctly
    mock_model.assert_called_once()

    # Assert that the response is structured correctly
    assert response.predicted_final_attendance == int(mock_prediction_value)

    # Assert that the confidence interval was calculated correctly (e.g., +/- 10%)
    assert response.confidence_interval["lower_bound"] == 463  # int(515 * 0.9)
    assert response.confidence_interval["upper_bound"] == 566  # int(515 * 1.1)


def test_calculate_roi_predicts_correctly():
    """
    Tests the ROI calculation with a standard set of financial inputs.
    """
    # 1. Arrange
    request = ROICalculationRequest(
        event_id="evt_123",
        total_costs=50000.0,
        current_registrations=300,
        ticket_price=200.0,
    )

    # 2. Act
    response = calculate_roi(request)

    # 3. Assert - UPDATED LOGIC
    # Logic:
    # Projected Attendees = 300 * 1.05 = 315
    # Predicted Revenue = 315 * 200 = 63000
    # Profit Projection = 63000 - 50000 = 13000
    # Predicted ROI = 13000 / 50000 = 0.26
    # Break-even = 50000 / 200 = 250 attendees
    assert response.profit_projection == 13000.0
    assert response.predicted_roi == 0.26
    assert response.break_even_point_attendees == 250


def test_calculate_roi_handles_zero_cost():
    """
    Tests the edge case where total_costs are zero to prevent division errors.
    """
    # 1. Arrange
    request = ROICalculationRequest(
        event_id="evt_123",
        total_costs=0.0,
        current_registrations=100,
        ticket_price=50.0,
    )

    # 2. Act
    response = calculate_roi(request)

    # 3. Assert
    # If costs are 0, ROI should be 0, and break-even is 0.
    assert response.predicted_roi == 0.0
    assert response.break_even_point_attendees == 0
    assert response.profit_projection == 5250.0  # (100 + 5 projected) * 50


def test_get_success_probability_calculates_correctly():
    """
    Tests that the success probability is calculated correctly based on a
    weighted average of input metrics.
    """
    # 1. Arrange
    # Provide a mix of high and low scores. Speaker quality is high, others are average/low.
    request = SuccessProbabilityRequest(
        event_id="evt_123",
        registration_rate=0.6,  # 60% of capacity registered
        speaker_quality_score=0.9,  # 9/10 speaker rating
        marketing_reach=5000,  # Reached 5000 people
    )

    # 2. Act
    response = get_success_probability(request)

    # 3. Assert
    # Logic (based on implementation weights):
    # reg_score = 0.6 * 0.4 = 0.24
    # speaker_score = 0.9 * 0.5 = 0.45
    # marketing_score = (5000 / 50000) * 0.1 = 0.1 * 0.1 = 0.01
    # total_score = 0.24 + 0.45 + 0.01 = 0.70
    assert response.success_probability == pytest.approx(0.70)

    # Assert that the response correctly identifies the key success and risk factors
    assert "High speaker quality score" in response.success_factors
    assert "Low marketing reach" in response.risk_factors
    assert "Average registration rate" in response.risk_factors


@pytest.mark.parametrize(
    "event_type, target_audience, expected_day_of_week_range, expected_time_range",
    [
        ("webinar", "Tech Professionals", range(0, 5), (time(9, 0), time(12, 0))),
        ("networking", "Tech Professionals", range(0, 5), (time(17, 0), time(20, 0))),
        # NEW TEST CASE: A high-value audience gets a different suggestion
        ("webinar", "C-Suite Executives", range(0, 5), (time(8, 0), time(10, 0))),
    ],
)
def test_get_optimal_timing_for_event_types(
    event_type, target_audience, expected_day_of_week_range, expected_time_range
):
    """
    Tests that the heuristic model suggests appropriate days and times
    for different event types. (Monday=0, Sunday=6)
    """
    # 1. Arrange
    request = EventTimingRequest(
        event_type=event_type, target_audience=target_audience, location="Global"
    )

    # 2. Act
    response = get_optimal_timing(request)

    # 3. Assert
    # Check that the suggested date is a valid weekday
    assert response.optimal_date.weekday() in expected_day_of_week_range

    # Check that the suggested time is within the expected range
    assert expected_time_range[0] <= response.optimal_time <= expected_time_range[1]

    # Check that the confidence score is a valid probability
    assert 0.0 <= response.confidence_score <= 1.0


def test_predict_engagement_ranks_sessions_correctly(mocker):
    """
    Tests that the engagement prediction service calls the model and
    correctly sorts and ranks the sessions by their predicted score.
    """
    # 1. Arrange
    # Define the sessions to be ranked
    sessions = [
        EngagementPredictionRequest.SessionInput(
            session_id="ses_1", topic="Introduction to Marketing"
        ),
        EngagementPredictionRequest.SessionInput(
            session_id="ses_2", topic="Advanced AI Techniques"
        ),
        EngagementPredictionRequest.SessionInput(
            session_id="ses_3", topic="Cloud Microservices"
        ),
    ]
    request = EngagementPredictionRequest(event_id="evt_123", sessions=sessions)

    # Mock the model's predict method to return a specific set of scores.
    # Note the order is intentionally different from the input order.
    mock_model = mocker.patch("app.features.analytics.service.engagement_model.predict")
    mock_model.return_value = [
        {"session_id": "ses_1", "score": 65.5},  # Marketing
        {"session_id": "ses_2", "score": 95.0},  # AI
        {"session_id": "ses_3", "score": 88.2},  # Microservices
    ]

    # 2. Act
    response = predict_engagement(request)

    # 3. Assert
    # The response should be sorted by score, descending.
    assert len(response.session_predictions) == 3

    # Check Rank 1: Advanced AI
    assert response.session_predictions[0].session_id == "ses_2"
    assert response.session_predictions[0].engagement_score == 95.0
    assert response.session_predictions[0].popularity_rank == 1

    # Check Rank 2: Cloud Microservices
    assert response.session_predictions[1].session_id == "ses_3"
    assert response.session_predictions[1].engagement_score == 88.2
    assert response.session_predictions[1].popularity_rank == 2

    # Check Rank 3: Intro to Marketing
    assert response.session_predictions[2].session_id == "ses_1"
    assert response.session_predictions[2].engagement_score == 65.5
    assert response.session_predictions[2].popularity_rank == 3
