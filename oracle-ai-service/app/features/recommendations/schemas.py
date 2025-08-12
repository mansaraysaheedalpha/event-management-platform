from pydantic import BaseModel, Field
from typing import List, Optional


class ContentRecommendationRequest(BaseModel):
    user_id: str
    event_id: str
    attended_sessions: Optional[List[str]] = []


class ContentRecommendationResponse(BaseModel):
    class RecommendedSession(BaseModel):
        session_id: str
        title: str
        relevance_score: float = Field(..., ge=0, le=1)
        recommendation_reasons: List[str]

    recommended_sessions: List[RecommendedSession]


class SpeakerRecommendationRequest(BaseModel):
    event_id: str
    topic: str
    target_audience: str


class SpeakerRecommendationResponse(BaseModel):
    class RecommendedSpeaker(BaseModel):
        speaker_id: str
        name: str
        expertise_match: float

    recommended_speakers: List[RecommendedSpeaker]
