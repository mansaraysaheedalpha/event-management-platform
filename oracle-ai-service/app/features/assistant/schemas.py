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
    is_processing: bool = Field(
        default=False,
        description="Indicates if the AI is currently processing. Should only be true during active query processing."
    )
    processing_status: Optional[str] = Field(
        default=None,
        description="Optional status message during processing (e.g., 'analyzing query', 'generating response')"
    )


class SmartNotificationRequest(BaseModel):
    user_id: str
    message: str


class SmartNotificationResponse(BaseModel):
    recommended_time: datetime
    confidence: float
