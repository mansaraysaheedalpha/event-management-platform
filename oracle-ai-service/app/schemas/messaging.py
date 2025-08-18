#app/schemas/messaging.py
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

# --- Input Schemas ---


class ChatMessagePayload(BaseModel):
    messageId: str
    eventId: str
    sessionId: Optional[str] = None
    userId: str
    text: str
    timestamp: datetime


class UserInteractionPayload(BaseModel):
    interactionId: str
    eventId: str
    sessionId: Optional[str] = None
    userId: str
    type: str
    timestamp: datetime


class AttendanceUpdatePayload(BaseModel):
    eventId: str
    sessionId: str
    currentAttendance: int
    timestamp: datetime


class SessionFeedbackPayload(BaseModel):
    feedbackId: str
    eventId: str
    sessionId: str
    userId: str
    rating: int
    comment: Optional[str] = None


class NetworkConnectionPayload(BaseModel):
    connectionId: str
    eventId: str
    user1_id: str  # Simplified from the spec for this example
    user2_id: str  # Simplified from the spec for this example


# --- Output (Prediction) Schemas ---


class SentimentScorePredictionPayload(BaseModel):
    sourceMessageId: str
    eventId: str
    sessionId: Optional[str] = None
    sentiment: str
    score: float
    confidence: float
    timestamp: datetime


class EngagementPredictionPayload(BaseModel):
    eventId: str
    sessionId: Optional[str] = None
    engagementScore: float
    trend: str
    timestamp: datetime


class CapacityForecastPredictionPayload(BaseModel):
    eventId: str
    sessionId: str
    forecastedAttendance: int
    overflowProbability: float
    alertLevel: str
    suggestion: str
    timestamp: datetime


class NetworkingSuggestionPayload(BaseModel):
    suggestionId: str
    eventId: str
    recipientUserId: str
    suggestedUserId: str  # Simplified from the spec for this example
    matchScore: float
    matchReasons: List[str]
    suggestedIceBreaker: str
    timestamp: datetime


class SuccessInsightPayload(BaseModel):
    insightId: str
    eventId: str
    title: str
    description: str
    severity: str
    data: dict
    timestamp: datetime
