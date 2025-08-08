from fastapi import APIRouter
from .schemas import *
from . import service

router = APIRouter()


@router.post(
    "/analysis/sentiment",
    response_model=SentimentAnalysisResponse,
    tags=["Sentiment & Behavior Analysis"],
)
def get_sentiment_analysis(request: SentimentAnalysisRequest):
    """
    Analyzes sentiment from a batch of text data.
    """
    return service.analyze_batch_sentiment(request)


@router.post(
    "/analysis/engagement-scoring",
    response_model=EngagementScoringResponse,
    tags=["Sentiment & Behavior Analysis"],
)
def get_engagement_scores(request: EngagementScoringRequest):
    """Scores user engagement levels in real-time."""
    return service.score_engagement(request)


@router.post(
    "/analysis/audience-segmentation",
    response_model=AudienceSegmentationResponse,
    tags=["Sentiment & Behavior Analysis"],
)
def get_audience_segmentation(request: AudienceSegmentationRequest):
    """Dynamically groups attendees based on behavior and preferences."""
    return service.segment_audience(request)


@router.post(
    "/analysis/behavioral-patterns",
    response_model=BehavioralPatternResponse,
    tags=["Sentiment & Behavior Analysis"],
)
def get_behavioral_patterns(request: BehavioralPatternRequest):
    """Identifies user journey patterns and behavior trends."""
    return service.analyze_behavior(request)
