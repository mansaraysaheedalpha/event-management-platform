from pydantic import BaseModel
from typing import List, Optional


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
