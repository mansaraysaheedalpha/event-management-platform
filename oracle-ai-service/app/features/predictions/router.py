#app/features/predictions/router.py
from fastapi import APIRouter
from .schemas import *
from . import service

router = APIRouter()


@router.post(
    "/predictions/churn-prediction",
    response_model=ChurnPredictionResponse,
    tags=["Advanced Predictions"],
)
def get_churn_prediction(request: ChurnPredictionRequest):
    """
    Identifies at-risk attendees who are likely to churn or disengage.
    """
    return service.predict_attendee_churn(request)


@router.post(
    "/predictions/event-creation",
    response_model=EventCreationPredictionResponse,
    tags=["Advanced Predictions"],
)
def get_event_creation_prediction(request: EventCreationPredictionRequest):
    """Suggests entire new events based on market trends."""
    return service.predict_event_creation(request)


@router.post(
    "/predictions/trend-tracking",
    response_model=TrendTrackingResponse,
    tags=["Advanced Predictions"],
)
def get_trend_tracking(request: TrendTrackingRequest):
    """Identifies emerging topics and trends."""
    return service.track_trends(request)


@router.post(
    "/predictions/crisis-prediction",
    response_model=CrisisPredictionResponse,
    tags=["Advanced Predictions"],
)
def get_crisis_prediction(request: CrisisPredictionRequest):
    """Predicts and helps manage potential event issues."""
    return service.predict_crisis(request)
