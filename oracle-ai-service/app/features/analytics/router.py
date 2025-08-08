from fastapi import APIRouter
from . import service
from .schemas import *

router = APIRouter()


@router.post(
    "/analytics/attendance-forecast",
    response_model=AttendanceForecastResponse,
    tags=["Predictive Analytics"],
)
def get_attendance_forecast(request: AttendanceForecastRequest):
    """
    Forecasts event attendance based on current data.
    The actual ML prediction is handled by the prediction service layer.
    """
    return service.forecast_attendance(request)


@router.post(
    "/analytics/roi-calculation",
    response_model=ROICalculationResponse,
    tags=["Predictive Analytics"],
)
def get_roi_calculation(request: ROICalculationRequest):
    """
    Predicts event profitability and ROI metrics.
    """
    return service.calculate_roi(request)


@router.post(
    "/analytics/event-timing",
    response_model=EventTimingResponse,
    tags=["Predictive Analytics"],
)
def get_event_timing(request: EventTimingRequest):
    """Predicts the best time to schedule an event."""
    return service.get_optimal_timing(request)


@router.post(
    "/analytics/success-probability",
    response_model=SuccessProbabilityResponse,
    tags=["Predictive Analytics"],
)
def get_success_prob(request: SuccessProbabilityRequest):
    """Calculates the likelihood of event success."""
    return service.get_success_probability(request)


@router.post(
    "/analytics/engagement-prediction",
    response_model=EngagementPredictionResponse,
    tags=["Predictive Analytics"],
)
def get_engagement_prediction(request: EngagementPredictionRequest):
    """Forecasts which sessions will be most popular."""
    return service.predict_engagement(request)
