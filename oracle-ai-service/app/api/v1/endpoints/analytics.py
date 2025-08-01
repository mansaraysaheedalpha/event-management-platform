from fastapi import APIRouter, Depends
from app.schemas.analytics import AttendanceForecastRequest, AttendanceForecastResponse
from app.services import prediction_service

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
    return prediction_service.forecast_attendance(request)
