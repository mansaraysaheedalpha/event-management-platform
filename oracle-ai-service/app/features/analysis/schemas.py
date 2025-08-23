# app/features/analysis/schemas.py
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime


class SentimentAnalysisRequest(BaseModel):
    class TextData(BaseModel):
        id: str
        text: str
        source: str

    text_data: List[TextData]


class SentimentAnalysisResponse(BaseModel):
    class SentimentResult(BaseModel):
        score: float = Field(..., ge=-1, le=1)
        label: str  # "positive", "negative", "neutral"

    class IndividualResult(BaseModel):
        id: str
        sentiment: "SentimentAnalysisResponse.SentimentResult"

    overall_sentiment: SentimentResult
    individual_results: List[IndividualResult]


class EngagementScoringRequest(BaseModel):
    class UserInteraction(BaseModel):
        user_id: str
        interaction_type: str
        session_id: Optional[str] = None

    user_interactions: List[UserInteraction]


class EngagementScoringResponse(BaseModel):
    class UserScore(BaseModel):
        user_id: str
        engagement_score: float
        engagement_level: str

    user_scores: List[UserScore]


class AudienceSegmentationRequest(BaseModel):
    event_id: str
    attendee_data: List[Dict[str, Any]]


class AudienceSegmentationResponse(BaseModel):
    class Segment(BaseModel):
        segment_id: str
        segment_name: str
        description: str
        size: int

    segments: List[Segment]


class BehavioralPatternRequest(BaseModel):
    event_id: str
    user_journeys: List[Dict[str, Any]]


class BehavioralPatternResponse(BaseModel):
    class Pattern(BaseModel):
        pattern_id: str
        pattern_name: str
        frequency: int  # The raw count of how many users followed this path
        path: List[str]
    common_patterns: List[Pattern]
