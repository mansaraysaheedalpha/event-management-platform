from pydantic import BaseModel
from typing import List, Optional
from datetime import date, time


class AttendanceForecastRequest(BaseModel):
    event_id: str
    current_registrations: int
    days_until_event: int
    marketing_spend: Optional[float] = None


class AttendanceForecastResponse(BaseModel):
    predicted_final_attendance: int
    confidence_interval: dict
    growth_trajectory: List[dict]
    factors_influencing: List[dict]


class ROICalculationRequest(BaseModel):
    event_id: str
    total_costs: float
    current_registrations: int
    ticket_price: float


class ROICalculationResponse(BaseModel):
    predicted_roi: float
    break_even_point_attendees: int
    profit_projection: float


class EventTimingRequest(BaseModel):
    event_type: str
    target_audience: str
    location: str


class EventTimingResponse(BaseModel):
    optimal_date: date
    optimal_time: time
    confidence_score: float


class SuccessProbabilityRequest(BaseModel):
    event_id: str
    registration_rate: float
    speaker_quality_score: float
    marketing_reach: int


class SuccessProbabilityResponse(BaseModel):
    success_probability: float
    success_factors: List[str]
    risk_factors: List[str]


class EngagementPredictionRequest(BaseModel):
    class SessionInput(BaseModel):
        session_id: str
        topic: str

    event_id: str
    sessions: List[SessionInput]


class EngagementPredictionResponse(BaseModel):
    class SessionPrediction(BaseModel):
        session_id: str
        engagement_score: float
        popularity_rank: int

    session_predictions: List[SessionPrediction]
