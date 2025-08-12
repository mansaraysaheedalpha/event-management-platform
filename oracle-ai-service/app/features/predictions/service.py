import random
from app.features.predictions.schemas import (
    ChurnPredictionRequest,
    ChurnPredictionResponse,
    EventCreationPredictionRequest,
    EventCreationPredictionResponse,
    TrendTrackingRequest,
    TrendTrackingResponse,
    CrisisPredictionRequest,
    CrisisPredictionResponse,
)


def predict_attendee_churn(request: ChurnPredictionRequest) -> ChurnPredictionResponse:
    """
    This service function predicts attendee churn risk.
    In a real system, this would use a classification model (e.g., Logistic Regression,
    Gradient Boosting) trained on historical engagement data.

    For now, we return a simulated, realistic response.
    """
    predictions = []
    for attendee in request.attendee_data:
        # Simple simulation: lower engagement = higher churn probability
        engagement_metric = attendee.sessions_attended + (
            attendee.chat_messages_sent * 0.5
        )
        churn_prob = max(0, 1 - (engagement_metric / 10))  # Normalize roughly
        churn_prob = round(random.uniform(churn_prob - 0.1, churn_prob + 0.1), 2)
        churn_prob = min(1.0, max(0.0, churn_prob))  # Clamp between 0 and 1

        risk_level = "low"
        if churn_prob > 0.7:
            risk_level = "high"
        elif churn_prob > 0.4:
            risk_level = "medium"

        predictions.append(
            ChurnPredictionResponse.ChurnPrediction(
                user_id=attendee.user_id,
                churn_probability=churn_prob,
                risk_level=risk_level,
            )
        )

    return ChurnPredictionResponse(churn_predictions=predictions)


def predict_event_creation(
    request: EventCreationPredictionRequest,
) -> EventCreationPredictionResponse:
    """Simulates suggesting entire new events based on market trends."""
    suggestions = [
        EventCreationPredictionResponse.SuggestedEvent(
            event_concept="AI in FinTech Summit 2026",
            target_audience="Financial Technologists and Executives",
            success_probability=0.88,
        ),
        EventCreationPredictionResponse.SuggestedEvent(
            event_concept="Decentralized Web Developers Conference",
            target_audience="Web3 and Blockchain Developers",
            success_probability=0.81,
        ),
    ]
    return EventCreationPredictionResponse(suggested_events=suggestions)


def track_trends(request: TrendTrackingRequest) -> TrendTrackingResponse:
    """Simulates identifying emerging topics and trends."""
    trends = [
        TrendTrackingResponse.Trend(
            trend_name="Hyper-Personalization in Events",
            growth_rate=0.45,
            maturity_level="growing",
        ),
        TrendTrackingResponse.Trend(
            trend_name="Sustainable Event Management",
            growth_rate=0.30,
            maturity_level="emerging",
        ),
    ]
    return TrendTrackingResponse(identified_trends=trends)


def predict_crisis(request: CrisisPredictionRequest) -> CrisisPredictionResponse:
    """Simulates predicting potential event issues."""
    predictions = [
        CrisisPredictionResponse.CrisisPrediction(
            crisis_type="logistical", probability=0.15, severity="medium"
        ),
        CrisisPredictionResponse.CrisisPrediction(
            crisis_type="technical", probability=0.05, severity="high"
        ),
    ]
    return CrisisPredictionResponse(crisis_predictions=predictions)
