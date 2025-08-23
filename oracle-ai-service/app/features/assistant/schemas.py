# app/features/assistant/schemas.py
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime


class ConciergeRequest(BaseModel):
    user_id: str
    query: str
    context: Optional[Dict[str, Any]] = None


class ConciergeResponse(BaseModel):
    class Action(BaseModel):
        action: str
        parameters: Dict[str, Any]

    response: str
    response_type: str  # text, action, redirect
    actions: List[Action] = []
    follow_up_questions: List[str] = []


class SmartNotificationRequest(BaseModel):
    user_id: str
    message: str


class SmartNotificationResponse(BaseModel):
    recommended_time: datetime
    confidence: float
