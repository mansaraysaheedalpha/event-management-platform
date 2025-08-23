# tests/features/test_recommendations_service.py

import pytest
from app.features.recommendations.service import *
from app.features.recommendations.schemas import *


def test_get_content_recommendations_matches_user_history(mocker):
    """
    Tests that the content recommender suggests sessions with topics
    related to the user's previously attended sessions.
    """
    # 1. Arrange
    # A user who has attended sessions about AI and Python.
    request = ContentRecommendationRequest(
        user_id="u1",
        event_id="evt_123",
        attended_sessions=["ses_ai_intro", "ses_python_basics"],
    )

    # Mock the DB call that fetches session topics.
    # This keeps our test fast and independent of the database.
    mock_session_db = {
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
    }
    mocker.patch(
        "app.features.recommendations.service._get_session_data_from_db",
        return_value=mock_session_db,
    )

    # 2. Act
    response = get_content_recommendations(request)

    # 3. Assert
    # The user should be recommended the two other AI/Python sessions.
    assert len(response.recommended_sessions) == 2

    recommended_ids = {rec.session_id for rec in response.recommended_sessions}
    assert recommended_ids == {"ses_advanced_ai", "ses_python_web"}

    # The session with the most specific match ("Advanced AI") should have a higher score.
    response.recommended_sessions.sort(key=lambda r: r.relevance_score, reverse=True)
    assert response.recommended_sessions[0].session_id == "ses_advanced_ai"


def test_recommend_speakers_ranks_by_combined_score(mocker):
    """
    Tests that the speaker recommender correctly scores and ranks speakers
    based on a weighted combination of topic expertise and audience fit.
    """
    # 1. Arrange
    # We need a technical speaker for an AI session.
    request = SpeakerRecommendationRequest(
        event_id="evt_123", topic="AI", target_audience="technical"
    )

    # Mock the speaker database.
    mock_speakers_db = [
        # Perfect fit: High AI expertise, technical audience fit.
        {
            "id": "spk_1",
            "name": "Dr. Eva Rostova",
            "expertise": ["AI", "ML"],
            "audience_fit": ["technical"],
        },
        # Good expertise, but wrong audience.
        {
            "id": "spk_2",
            "name": "John CEO",
            "expertise": ["AI", "Business"],
            "audience_fit": ["executive"],
        },
        # Wrong expertise, but right audience.
        {
            "id": "spk_3",
            "name": "DevOps Dan",
            "expertise": ["DevOps"],
            "audience_fit": ["technical"],
        },
        # Another perfect fit, but slightly less expertise.
        {
            "id": "spk_4",
            "name": "Anna Coder",
            "expertise": ["AI"],
            "audience_fit": ["technical"],
        },
    ]
    mocker.patch(
        "app.features.recommendations.service._get_all_speakers_from_db",
        return_value=mock_speakers_db,
    )

    # 2. Act
    response = recommend_speakers(request)

    # 3. Assert

    assert len(response.recommended_speakers) == 4

    # Logic: Score = (Expertise * 0.7) + (Audience * 0.3)
    # spk_1: (1.0 * 0.7) + (1.0 * 0.3) = 1.0
    # spk_4: (1.0 * 0.7) + (1.0 * 0.3) = 1.0
    # spk_2: (1.0 * 0.7) + (0.0 * 0.3) = 0.7

    # Check Rank 1 & 2 (can be spk_1 or spk_4)
    top_two_ids = {
        response.recommended_speakers[0].speaker_id,
        response.recommended_speakers[1].speaker_id,
    }
    assert top_two_ids == {"spk_1", "spk_4"}
    assert response.recommended_speakers[0].match_score == 1.0
    assert response.recommended_speakers[1].match_score == 1.0

    # Check Rank 3
    assert response.recommended_speakers[2].speaker_id == "spk_2"
    assert response.recommended_speakers[2].match_score == pytest.approx(0.7)
