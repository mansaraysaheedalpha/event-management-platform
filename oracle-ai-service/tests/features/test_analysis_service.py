# tests/features/test_analysis_service.py
import pytest
from app.features.analysis.service import *
from app.features.analysis.schemas import *


def test_score_engagement_calculates_correctly():
    """
    Tests that the engagement scoring logic correctly calculates scores
    based on a weighted system and assigns the correct engagement level.
    """
    # Define a list of interactions for multiple users
    interactions = [
        # User 1: Should be HIGH engagement (5 + 3 + 1 = 9)
        EngagementScoringRequest.UserInteraction(
            user_id="user_1", interaction_type="question_upvote"
        ),
        EngagementScoringRequest.UserInteraction(
            user_id="user_1", interaction_type="poll_vote"
        ),
        EngagementScoringRequest.UserInteraction(
            user_id="user_1", interaction_type="click"
        ),
        # User 2: Should be MEDIUM engagement (3 + 1 = 4)
        EngagementScoringRequest.UserInteraction(
            user_id="user_2", interaction_type="poll_vote"
        ),
        EngagementScoringRequest.UserInteraction(
            user_id="user_2", interaction_type="click"
        ),
        # User 3: Should be LOW engagement (1)
        EngagementScoringRequest.UserInteraction(
            user_id="user_3", interaction_type="click"
        ),
        # User 4: No scoreable interactions
        EngagementScoringRequest.UserInteraction(
            user_id="user_4", interaction_type="scroll"
        ),
    ]

    request = EngagementScoringRequest(user_interactions=interactions)
    response = score_engagement(request)

    # Create a dictionary for easy lookup of scores by user_id
    scores_by_user = {score.user_id: score for score in response.user_scores}

    # Assert that we got scores for the 3 users with valid interactions
    assert len(response.user_scores) == 3

    # Assert User 1's score and level are correct
    assert scores_by_user["user_1"].engagement_score == 9
    assert scores_by_user["user_1"].engagement_level == "high"

    # Assert User 2's score and level are correct
    assert scores_by_user["user_2"].engagement_score == 4
    assert scores_by_user["user_2"].engagement_level == "medium"

    # Assert User 3's score and level are correct
    assert scores_by_user["user_3"].engagement_score == 1
    assert scores_by_user["user_3"].engagement_level == "low"

    # Assert User 4 is not in the results because "scroll" is not a scored interaction
    assert "user_4" not in scores_by_user


def test_segment_audience_groups_users_correctly():
    """
    Tests that the K-Means clustering logic correctly segments users
    based on their engagement scores.
    """
    # Create a list of attendees with distinct engagement groups
    attendees = [
        # Group 1: Low Engagement
        {"user_id": "user_101", "engagement_score": 5},
        {"user_id": "user_102", "engagement_score": 8},
        # Group 2: High Engagement
        {"user_id": "user_201", "engagement_score": 92},
        {"user_id": "user_202", "engagement_score": 98},
        {"user_id": "user_203", "engagement_score": 100},
    ]

    request = AudienceSegmentationRequest(event_id="evt_123", attendee_data=attendees)
    response = segment_audience(request)

    # We expect two segments: "Low Engagement" and "High Engagement"
    assert len(response.segments) == 2

    # Sort segments by size to make assertions predictable
    response.segments.sort(key=lambda s: s.size)

    low_engagement_segment = response.segments[0]
    high_engagement_segment = response.segments[1]

    # Assert the low engagement segment is correct
    assert low_engagement_segment.size == 2
    assert "Low" in low_engagement_segment.segment_name

    # Assert the high engagement segment is correct
    assert high_engagement_segment.size == 3
    assert "High" in high_engagement_segment.segment_name


def test_analyze_behavior_identifies_common_patterns():
    """
    Tests that the Trie-based analysis correctly identifies the most
    frequent user journey from a list of sequences.
    """
    # Define user journeys. The most common pattern is A -> B -> C.
    journeys = [
        {"user_id": "u1", "journey": ["A", "B", "C"]},
        {"user_id": "u2", "journey": ["A", "B", "D"]},
        {"user_id": "u3", "journey": ["A", "B", "C"]},
        {"user_id": "u4", "journey": ["X", "Y"]},
        {"user_id": "u5", "journey": ["A", "B", "C"]},
    ]

    request = BehavioralPatternRequest(event_id="evt_123", user_journeys=journeys)
    response = analyze_behavior(request)

    # There should be 3 unique patterns identified
    assert len(response.common_patterns) == 3

    # Sort by frequency to make assertions predictable
    response.common_patterns.sort(key=lambda p: p.frequency, reverse=True)

    # The top pattern should be A -> B -> C with a frequency of 3/5 = 0.6
    top_pattern = response.common_patterns[0]
    assert top_pattern.pattern_name == "A → B → C"
    assert top_pattern.frequency == 3
    assert top_pattern.path == ["A", "B", "C"]

    # The other patterns should have a frequency of 1
    assert response.common_patterns[1].frequency == 1
    assert response.common_patterns[2].frequency == 1
