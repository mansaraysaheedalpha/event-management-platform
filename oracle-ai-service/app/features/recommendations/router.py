# app/features/recommendations/router.py
from fastapi import APIRouter
from .schemas import *
from . import service

router = APIRouter()


@router.post(
    "/recommendations/content",
    response_model=ContentRecommendationResponse,
    tags=["Recommendations"],
)
def get_content_recommendations(request: ContentRecommendationRequest):
    """
    Provides personalized session and content recommendations for a user.
    """
    return service.get_content_recommendations(request)


@router.post(
    "/recommendations/speakers",
    response_model=SpeakerRecommendationResponse,
    tags=["Recommendations"],
)
def get_speaker_recommendations(request: SpeakerRecommendationRequest):
    """Provides AI-powered speaker suggestions for an event."""
    return service.recommend_speakers(request)
