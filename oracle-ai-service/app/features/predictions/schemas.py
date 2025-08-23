# app/features/predictions/schemas.py
from pydantic import BaseModel, Field
from typing import List, Optional


class ChurnPredictionRequest(BaseModel):
    class AttendeeData(BaseModel):
        user_id: str
        # In a real model, you'd have many more features here
        sessions_attended: int
        chat_messages_sent: int

    event_id: str
    attendee_data: List[AttendeeData]


class ChurnPredictionResponse(BaseModel):
    class ChurnPrediction(BaseModel):
        user_id: str
        churn_probability: float = Field(..., ge=0, le=1)
        risk_level: str  # low, medium, high

    churn_predictions: List[ChurnPrediction]


class EventCreationPredictionRequest(BaseModel):
    organization_id: str
    market_context: dict


class EventCreationPredictionResponse(BaseModel):
    class SuggestedEvent(BaseModel):
        event_concept: str
        target_audience: str
        success_probability: float

    suggested_events: List[SuggestedEvent]


class TrendTrackingRequest(BaseModel):
    industry: str
    time_horizon: str


class TrendTrackingResponse(BaseModel):
    class Trend(BaseModel):
        trend_name: str
        growth_rate: float
        maturity_level: str

    identified_trends: List[Trend]


class CrisisPredictionRequest(BaseModel):
    event_id: str
    monitoring_data: dict


class CrisisPredictionResponse(BaseModel):
    class CrisisPrediction(BaseModel):
        crisis_type: str
        probability: float
        severity: str

    crisis_predictions: List[CrisisPrediction]
