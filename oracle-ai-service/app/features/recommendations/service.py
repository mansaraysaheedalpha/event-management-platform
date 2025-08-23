# app/features/recommendations/service.py

from typing import List, Dict, Any, Set
from .schemas import (
    ContentRecommendationRequest,
    ContentRecommendationResponse,
    SpeakerRecommendationRequest,
    SpeakerRecommendationResponse,
)


def _get_session_data_from_db(event_id: str) -> Dict[str, Any]:
    """Simulates fetching all session data for an event from a database."""
    print(f"Simulating DB query for sessions in event: {event_id}")
    return {
        "ses_ai_intro": {
            "id": "ses_ai_intro",
            "title": "Intro to AI",
            "tags": ["AI", "ML"],
        },
        "ses_python_basics": {
            "id": "ses_python_basics",
            "title": "Python 101",
            "tags": ["Python"],
        },
        "ses_advanced_ai": {
            "id": "ses_advanced_ai",
            "title": "Advanced AI",
            "tags": ["AI", "Deep Learning"],
        },
        "ses_marketing": {
            "id": "ses_marketing",
            "title": "Marketing Today",
            "tags": ["Marketing"],
        },
        "ses_python_web": {
            "id": "ses_python_web",
            "title": "Web Apps with Python",
            "tags": ["Python", "WebDev"],
        },
        "ses_cloud": {
            "id": "ses_cloud",
            "title": "Cloud Native Apps",
            "tags": ["Cloud", "Kubernetes"],
        },
    }


def get_content_recommendations(
    request: ContentRecommendationRequest,
) -> ContentRecommendationResponse:
    """
    Recommends sessions to a user based on the tags of sessions
    they have already attended.
    """
    all_sessions = _get_session_data_from_db(request.event_id)
    attended_session_ids = set(request.attended_sessions)

    # 1. Build the User's Interest Profile
    # Collect all tags from the sessions the user has attended.
    user_interest_tags: Set[str] = set()
    for session_id in attended_session_ids:
        if session_id in all_sessions:
            user_interest_tags.update(all_sessions[session_id].get("tags", []))

    if not user_interest_tags:
        return ContentRecommendationResponse(
            recommended_sessions=[]
        )  # No basis for recommendation

    # 2. Score potential sessions based on interest overlap
    scored_sessions = []
    for session_id, session_data in all_sessions.items():
        # Don't recommend sessions the user has already attended
        if session_id in attended_session_ids:
            continue

        session_tags = set(session_data.get("tags", []))
        common_tags = user_interest_tags.intersection(session_tags)
        score = len(common_tags)

        if score > 0:
            scored_sessions.append(
                {
                    "session_id": session_id,
                    "title": session_data.get("title", ""),
                    "score": score,
                    "reasons": list(common_tags),
                }
            )

    # 3. Sort by score and return the top recommendations
    scored_sessions.sort(key=lambda s: s["score"], reverse=True)

    recommendations = [
        ContentRecommendationResponse.RecommendedSession(
            session_id=s["session_id"],
            title=s["title"],
            relevance_score=s["score"],
            recommendation_reasons=[
                f"Based on your interest in {reason}" for reason in s["reasons"]
            ],
        )
        for s in scored_sessions
    ]

    return ContentRecommendationResponse(recommended_sessions=recommendations)


def _get_all_speakers_from_db() -> List[Dict[str, Any]]:
    """Simulates fetching all potential speakers from a database."""
    return [
        {
            "id": "spk_1",
            "name": "Dr. Eva Rostova",
            "expertise": ["AI", "ML"],
            "audience_fit": ["technical"],
        },
        {
            "id": "spk_2",
            "name": "John CEO",
            "expertise": ["AI", "Business"],
            "audience_fit": ["executive"],
        },
        {
            "id": "spk_3",
            "name": "DevOps Dan",
            "expertise": ["DevOps"],
            "audience_fit": ["technical"],
        },
        {
            "id": "spk_4",
            "name": "Anna Coder",
            "expertise": ["AI"],
            "audience_fit": ["technical"],
        },
    ]


def recommend_speakers(
    request: SpeakerRecommendationRequest,
) -> SpeakerRecommendationResponse:
    """Recommends speakers using a weighted, multi-factor scoring model."""
    all_speakers = _get_all_speakers_from_db()

    # Define weights for our scoring model
    WEIGHTS = {"expertise": 0.7, "audience": 0.3}

    scored_speakers = []
    for speaker in all_speakers:
        # 1. Calculate Expertise Score (binary: 1 if the topic is present, 0 otherwise)
        expertise_score = 1.0 if request.topic in speaker.get("expertise", []) else 0.0

        # 2. Calculate Audience Fit Score (binary)
        audience_score = (
            1.0 if request.target_audience in speaker.get("audience_fit", []) else 0.0
        )

        # 3. Calculate the final weighted score
        combined_score = (expertise_score * WEIGHTS["expertise"]) + (
            audience_score * WEIGHTS["audience"]
        )

        if combined_score > 0:
            scored_speakers.append(
                {"id": speaker["id"], "name": speaker["name"], "score": combined_score}
            )

    # Sort by the final score
    scored_speakers.sort(key=lambda s: s["score"], reverse=True)

    recommendations = [
        SpeakerRecommendationResponse.RecommendedSpeaker(
            speaker_id=s["id"], name=s["name"], match_score=s["score"]
        )
        for s in scored_speakers
    ]

    return SpeakerRecommendationResponse(recommended_speakers=recommendations)
