# app/features/predictions/service.py
import random
from .schemas import (
    ChurnPredictionRequest,
    ChurnPredictionResponse,
    EventCreationPredictionRequest,
    EventCreationPredictionResponse,
    TrendTrackingRequest,
    TrendTrackingResponse,
    CrisisPredictionRequest,
    CrisisPredictionResponse,
)
from app.models.ml.churn import churn_model


def predict_attendee_churn(request: ChurnPredictionRequest) -> ChurnPredictionResponse:
    """
    Identifies at-risk attendees by predicting their churn probability using
    a pre-trained classification model.
    """
    if not request.attendee_data:
        return ChurnPredictionResponse(churn_predictions=[])

    # 1. Get churn probabilities from our model manager
    probabilities = churn_model.predict_proba(request.attendee_data)

    # 2. Process the results and assign a risk level
    predictions = []
    for i, attendee in enumerate(request.attendee_data):
        # The model returns [prob_not_churn, prob_churn], we want the second value
        churn_prob = probabilities[i][1]

        risk_level = "low"
        if churn_prob > 0.75:
            risk_level = "high"
        elif churn_prob > 0.5:
            risk_level = "medium"

        predictions.append(
            ChurnPredictionResponse.ChurnPrediction(
                user_id=attendee.user_id,
                churn_probability=churn_prob,
                risk_level=risk_level,
            )
        )

    return ChurnPredictionResponse(churn_predictions=predictions)


def _get_knowledge_base() -> dict:
    """
    Simulates fetching a curated knowledge base of industry trends and formats.
    In a real system, this could be a YAML file or a database table updated by experts.
    """
    return {
        "Tech": {
            "trends": ["Generative AI", "Quantum Computing", "Web3"],
            "formats": ["Virtual Summit", "Hackathon", "Developer Conference"],
        },
        "Finance": {
            "trends": ["DeFi", "Sustainable Investing", "Fintech Regulation"],
            "formats": ["Executive Forum", "Investor Pitch Day", "Roundtable"],
        },
        "Healthcare": {
            "trends": ["Telemedicine", "AI in Diagnostics", "Personalized Medicine"],
            "formats": ["Research Symposium", "Medical Conference", "Policy Summit"],
        },
    }


def predict_event_creation(
    request: EventCreationPredictionRequest,
) -> EventCreationPredictionResponse:
    """
    Generates new event concepts using a knowledge-based system.
    """
    knowledge_base = _get_knowledge_base()
    industry = request.market_context.get("industry")

    if not industry or industry not in knowledge_base:
        return EventCreationPredictionResponse(suggested_events=[])

    industry_data = knowledge_base[industry]

    # Randomly select a trend and format to generate a concept
    trend = random.choice(industry_data["trends"])
    event_format = random.choice(industry_data["formats"])

    # Generate the event concept
    event_concept = f"The {trend} {event_format} 2026"

    # Simulate a success probability
    success_prob = random.uniform(0.75, 0.95)

    suggestion = EventCreationPredictionResponse.SuggestedEvent(
        event_concept=event_concept,
        target_audience=f"Professionals in the {industry} and {trend} sectors.",
        success_probability=round(success_prob, 2),
    )

    return EventCreationPredictionResponse(suggested_events=[suggestion])


def track_trends(request: TrendTrackingRequest) -> TrendTrackingResponse:
    """
    Retrieves and formats emerging trend data from the knowledge base.
    """
    knowledge_base = _get_knowledge_base()
    industry = request.industry

    if not industry or industry not in knowledge_base:
        return TrendTrackingResponse(identified_trends=[])

    trends_data = knowledge_base[industry].get("trends", [])

    identified_trends = [
        TrendTrackingResponse.Trend(
            trend_name=trend["name"],
            growth_rate=trend["growth"],
            maturity_level=trend["maturity"],
        )
        for trend in trends_data
    ]

    return TrendTrackingResponse(identified_trends=identified_trends)


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


def predict_crisis(request: CrisisPredictionRequest) -> CrisisPredictionResponse:
    """
    Predicts potential event crises using a rules-based risk assessment engine.
    """
    data = request.monitoring_data
    crisis_scores = {"logistical": 0.0, "technical": 0.0, "safety": 0.0}

    # --- Risk Assessment Rules Engine ---

    # Rule 1: Long check-in queues indicate a logistical problem.
    queue_time = data.get("check_in_queue_minutes", 0)
    if queue_time > 20:
        crisis_scores["logistical"] += 0.8  # Critical risk
    elif queue_time > 10:
        crisis_scores["logistical"] += 0.4  # Medium risk

    # Rule 2: High Wi-Fi latency indicates a technical problem.
    wifi_latency = data.get("wifi_latency_ms", 0)
    if wifi_latency > 1500:
        crisis_scores["technical"] += 0.7  # High risk
    elif wifi_latency > 800:
        crisis_scores["technical"] += 0.3  # Medium risk

    # Rule 3: Very negative sentiment can indicate a logistical or safety issue.
    sentiment = data.get("attendee_sentiment_score", 0.0)
    if sentiment < -0.7:
        crisis_scores["logistical"] += 0.2
        crisis_scores["safety"] += 0.3

    # --- Format the Response ---
    predictions = []
    for crisis_type, probability in crisis_scores.items():
        if probability > 0:
            severity = "low"
            if probability > 0.7:
                severity = "high"
            elif probability > 0.4:
                severity = "medium"

            # Cap the probability at a realistic 0.95
            final_prob = min(probability, 0.95)

            predictions.append(
                CrisisPredictionResponse.CrisisPrediction(
                    crisis_type=crisis_type,
                    probability=final_prob,
                    severity=severity,
                )
            )

    return CrisisPredictionResponse(crisis_predictions=predictions)
