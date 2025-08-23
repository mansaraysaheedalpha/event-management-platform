# tests/features/test_networking_service.py

import pytest
from app.features.networking.service import *
from app.features.networking.schemas import *

# Define a fixture to create user profiles for tests
@pytest.fixture
def user_profiles():
    return [
        MatchmakingRequest.UserProfile(
            user_id="user_1", interests=["Python", "API Design", "FastAPI"]
        ),
        MatchmakingRequest.UserProfile(
            user_id="user_2", interests=["Python", "React", "JavaScript"]
        ),
        MatchmakingRequest.UserProfile(
            user_id="user_3", interests=["API Design", "Docker", "Kubernetes"]
        ),
        MatchmakingRequest.UserProfile(user_id="user_4", interests=["Go", "gRPC"]),
        MatchmakingRequest.UserProfile(
            user_id="user_5", interests=["Python", "API Design", "FastAPI"]
        ),  # Duplicate of user_1
    ]


def test_get_networking_matches_calculates_scores_correctly(user_profiles):
    """
    Verify that the Jaccard similarity scores are calculated correctly.
    """
    primary_user = user_profiles[0]
    other_users = user_profiles[1:]

    request = MatchmakingRequest(
        primary_user=primary_user, other_users=other_users, max_matches=10
    )

    response = get_networking_matches(request)

    # Expected scores:
    # user_2: common={Python}, union={Python, API Design, FastAPI, React, JavaScript} -> 1/5 = 0.2
    # user_3: common={API Design}, union={Python, API Design, FastAPI, Docker, Kubernetes} -> 1/5 = 0.2
    # user_4: common={}, union={...} -> 0/5 = 0.0 (should not be in results)
    # user_5: common={Python, API Design, FastAPI}, union={Python, API Design, FastAPI} -> 3/3 = 1.0

    assert len(response.matches) == 3

    # The results should be sorted by score descending
    assert response.matches[0].user_id == "user_5"
    assert response.matches[0].match_score == 1.0
    assert "Python" in response.matches[0].common_interests

    # The next two have the same score, their order doesn't matter
    user_ids_for_0_2_score = {response.matches[1].user_id, response.matches[2].user_id}
    assert user_ids_for_0_2_score == {"user_2", "user_3"}
    assert response.matches[1].match_score == 0.2
    assert response.matches[2].match_score == 0.2


def test_get_networking_matches_respects_max_matches_limit(user_profiles):
    """
    Verify that the function returns only the number of matches specified.
    """
    primary_user = user_profiles[0]
    other_users = user_profiles[1:]

    request = MatchmakingRequest(
        primary_user=primary_user,
        other_users=other_users,
        max_matches=1,  # Limit to only the top match
    )

    response = get_networking_matches(request)

    assert len(response.matches) == 1
    assert response.matches[0].user_id == "user_5"


def test_get_networking_matches_handles_no_common_interests(user_profiles):
    """
    Verify that no matches are returned if there are no common interests.
    """
    primary_user = MatchmakingRequest.UserProfile(
        user_id="user_new", interests=["Rust", "Wasm"]
    )

    request = MatchmakingRequest(
        primary_user=primary_user, other_users=user_profiles, max_matches=10
    )

    response = get_networking_matches(request)
    assert len(response.matches) == 0


def test_get_networking_matches_does_not_match_self(user_profiles):
    """
    Verify that a user is not matched with themselves, even if they appear in the list.
    """
    primary_user = user_profiles[0]

    # user_profiles includes user_1, who is the primary user
    request = MatchmakingRequest(
        primary_user=primary_user, other_users=user_profiles, max_matches=10
    )

    response = get_networking_matches(request)

    # Ensure 'user_1' is not in the list of matched user IDs
    matched_user_ids = {match.user_id for match in response.matches}
    assert primary_user.user_id not in matched_user_ids


def test_get_conversation_starters_are_dynamic_and_relevant():
    """
    Tests that the conversation starters are dynamically generated
    and incorporate the shared interests provided.
    """
    # 1. Arrange
    common_interests = ["AI", "API Design"]
    request = ConversationStarterRequest(
        user1_id="u1", user2_id="u2", common_interests=common_interests
    )

    # 2. Act
    response = get_conversation_starters(request)

    # 3. Assert
    # The function should return a non-empty list of suggestions
    assert len(response.conversation_starters) > 0

    # Check that at least one of the suggestions contains a shared interest
    found_interest = False
    for starter in response.conversation_starters:
        assert isinstance(starter, str)  # Ensure it's a string
        if "AI" in starter or "API Design" in starter:
            found_interest = True
            break

    assert found_interest, "No generated starter contained a relevant shared interest."


def test_get_booth_suggestions_recommends_and_ranks_correctly(mocker):
    """
    Tests that the booth suggestion service correctly calculates a relevance
    score and returns a ranked list of the most relevant booths.
    """
    # 1. Arrange
    # A user interested in AI, Cloud, and Data.
    user_interests = ["AI", "Cloud", "Data"]
    request = BoothSuggestionRequest(
        user_id="u1", event_id="evt_123", user_interests=user_interests
    )

    # Mock our data source for booths. In a real app, this would be a database call.
    mock_booths_db = [
        {
            "booth_id": "booth_1",
            "name": "AI Solutions Inc.",
            "tags": ["AI", "Machine Learning"],
        },
        {
            "booth_id": "booth_2",
            "name": "CloudCorp",
            "tags": ["Cloud", "DevOps", "Data"],
        },
        {
            "booth_id": "booth_3",
            "name": "Legacy Systems",
            "tags": ["Hardware", "On-Prem"],
        },
        {
            "booth_id": "booth_4",
            "name": "Data Insights LLC",
            "tags": ["Data", "Analytics", "AI"],
        },
    ]
    mocker.patch(
        "app.features.networking.service._get_all_booths_from_db",
        return_value=mock_booths_db,
    )

    # 2. Act
    response = get_booth_suggestions(request)

    # 3. Assert
    # We expect 3 suggestions, as "Legacy Systems" has no matching tags.
    assert len(response.suggested_booths) == 3

    # Expected Scores:
    # booth_4: "Data", "AI" (2 matches) -> Score 2
    # booth_2: "Cloud", "Data" (2 matches) -> Score 2
    # booth_1: "AI" (1 match) -> Score 1

    # Assert Rank 1 & 2 (order can vary between booths with same score)
    top_two_ids = {
        response.suggested_booths[0].booth_id,
        response.suggested_booths[1].booth_id,
    }
    assert top_two_ids == {"booth_2", "booth_4"}
    assert response.suggested_booths[0].relevance_score == 2
    assert response.suggested_booths[1].relevance_score == 2

    # Assert Rank 3
    assert response.suggested_booths[2].booth_id == "booth_1"
    assert response.suggested_booths[2].relevance_score == 1
