import random
from app.features.recommendations.schemas import (
    ContentRecommendationRequest,
    ContentRecommendationResponse,
    SpeakerRecommendationRequest,
    SpeakerRecommendationResponse,
)


def get_content_recommendations(
    request: ContentRecommendationRequest,
) -> ContentRecommendationResponse:
    """
    This service function generates personalized content recommendations.
    In a real system, this would use a content-based or collaborative
    filtering model to match user profiles with session content.

    For now, we return a hardcoded, realistic response.
    """
    recommendations = [
        ContentRecommendationResponse.RecommendedSession(
            session_id=f"ses_{random.randint(1000, 9999)}",
            title="Advanced Microservice Architecture",
            relevance_score=round(random.uniform(0.8, 0.98), 2),
            recommendation_reasons=[
                "Based on your interest in 'Scalability'.",
                "Matches your role as a 'Software Engineer'.",
            ],
        ),
        ContentRecommendationResponse.RecommendedSession(
            session_id=f"ses_{random.randint(1000, 9999)}",
            title="Real-Time Data with Kafka",
            relevance_score=round(random.uniform(0.7, 0.9), 2),
            recommendation_reasons=[
                "Based on your attendance at 'Intro to Event-Driven Systems'."
            ],
        ),
    ]

    return ContentRecommendationResponse(recommended_sessions=recommendations)


def recommend_speakers(
    request: SpeakerRecommendationRequest,
) -> SpeakerRecommendationResponse:
    """Simulates recommending speakers for an event."""
    recommendations = [
        SpeakerRecommendationResponse.RecommendedSpeaker(
            speaker_id=f"spk_{random.randint(1000, 9999)}",
            name="Dr. Evelyn Reed",
            expertise_match=round(random.uniform(0.85, 0.99), 2),
        ),
        SpeakerRecommendationResponse.RecommendedSpeaker(
            speaker_id=f"spk_{random.randint(1000, 9999)}",
            name="Kenji Tanaka",
            expertise_match=round(random.uniform(0.80, 0.95), 2),
        ),
    ]
    return SpeakerRecommendationResponse(recommended_speakers=recommendations)
