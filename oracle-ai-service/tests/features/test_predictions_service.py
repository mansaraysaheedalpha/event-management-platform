# tests/features/test_predictions_service.py

import pytest
import numpy as np
from app.features.predictions.service import *
from app.features.predictions.schemas import *


def test_predict_attendee_churn_classifies_risk_correctly(mocker):
    """
    Tests that the churn prediction service correctly uses a classification
    model and assigns a risk level based on the predicted churn probability.
    """
    # 1. Arrange
    # A list of attendees with different engagement levels
    attendees = [
        # This user is highly engaged, should have low churn risk
        ChurnPredictionRequest.AttendeeData(
            user_id="user_1", sessions_attended=8, chat_messages_sent=20
        ),
        # This user is disengaged, should have high churn risk
        ChurnPredictionRequest.AttendeeData(
            user_id="user_2", sessions_attended=1, chat_messages_sent=0
        ),
    ]
    request = ChurnPredictionRequest(event_id="evt_123", attendee_data=attendees)

    # Mock the model's `predict_proba` method. Scikit-learn classifiers use
    # this to return an array of [prob_class_0, prob_class_1] for each input.
    # Let's say class 1 is "churn".
    mock_model = mocker.patch(
        "app.features.predictions.service.churn_model.predict_proba"
    )
    mock_model.return_value = np.array(
        [
            [0.95, 0.05],  # user_1: 95% prob of NOT churning, 5% prob of churning
            [0.10, 0.90],  # user_2: 10% prob of NOT churning, 90% prob of churning
        ]
    )

    # 2. Act
    response = predict_attendee_churn(request)

    # 3. Assert
    assert len(response.churn_predictions) == 2
    predictions = {p.user_id: p for p in response.churn_predictions}

    # Check the low-risk user
    assert predictions["user_1"].churn_probability == pytest.approx(0.05)
    assert predictions["user_1"].risk_level == "low"

    # Check the high-risk user
    assert predictions["user_2"].churn_probability == pytest.approx(0.90)
    assert predictions["user_2"].risk_level == "high"


def test_predict_event_creation_generates_relevant_concepts(mocker):
    """
    Tests that the event creation service uses its knowledge base to generate
    a relevant event concept for a given industry.
    """
    # 1. Arrange
    request = EventCreationPredictionRequest(
        organization_id="org_123", market_context={"industry": "Tech"}
    )

    # Mock the knowledge base to return a predictable set of trends for "Tech"
    mock_kb = {
        "Tech": {
            "trends": ["Generative AI", "Quantum Computing"],
            "formats": ["Virtual Summit", "Hackathon"],
        }
    }
    mocker.patch(
        "app.features.predictions.service._get_knowledge_base", return_value=mock_kb
    )

    # 2. Act
    response = predict_event_creation(request)

    # 3. Assert
    assert len(response.suggested_events) > 0

    # Check that the generated concept is relevant
    concept_title = response.suggested_events[0].event_concept.lower()
    assert "generative ai" in concept_title or "quantum computing" in concept_title
    assert "summit" in concept_title or "hackathon" in concept_title

    # Check that the probability score is valid
    assert 0.0 <= response.suggested_events[0].success_probability <= 1.0


def test_track_trends_retrieves_data_from_knowledge_base(mocker):
    """
    Tests that the trend tracking service correctly looks up an industry
    in the knowledge base and returns the associated trend data.
    """
    # 1. Arrange
    request = TrendTrackingRequest(industry="Finance", time_horizon="short_term")

    # Mock the knowledge base to provide predictable data for the "Finance" industry
    mock_kb = {
        "Finance": {
            "trends": [
                {"name": "DeFi", "growth": 0.6, "maturity": "growing"},
                {"name": "Sustainable Investing", "growth": 0.4, "maturity": "mature"},
            ]
        }
    }
    mocker.patch(
        "app.features.predictions.service._get_knowledge_base", return_value=mock_kb
    )

    # 2. Act
    response = track_trends(request)

    # 3. Assert
    assert len(response.identified_trends) == 2

    # Check the DeFi trend data
    defi_trend = next(t for t in response.identified_trends if t.trend_name == "DeFi")
    assert defi_trend.growth_rate == 0.6
    assert defi_trend.maturity_level == "growing"


def test_predict_crisis_identifies_risk_from_monitoring_data():
    """
    Tests that the risk assessment engine correctly identifies potential
    crises by applying rules to incoming monitoring data.
    """
    # 1. Arrange
    # This data shows a very long check-in queue, signaling a logistical issue.
    monitoring_data = {
        "check_in_queue_minutes": 25,
        "wifi_latency_ms": 150,
        "attendee_sentiment_score": -0.2,
    }
    request = CrisisPredictionRequest(
        event_id="evt_123", monitoring_data=monitoring_data
    )

    # 2. Act
    response = predict_crisis(request)

    # 3. Assert
    # We expect one crisis (logistical) to be predicted.
    assert len(response.crisis_predictions) == 1

    prediction = response.crisis_predictions[0]
    assert prediction.crisis_type == "logistical"
    assert prediction.severity == "high"
    # The probability should be high, based on the 25-minute queue.
    assert prediction.probability > 0.7
