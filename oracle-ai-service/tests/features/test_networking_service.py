import pytest
from app.features.networking.schemas import MatchmakingRequest
from app.features.networking.service import get_networking_matches
from .test_data import primary_user, matchmaking_test_cases


@pytest.mark.parametrize(
    "other_user, expected_score, expected_common", matchmaking_test_cases
)
def test_matchmaking_scenarios(other_user, expected_score, expected_common):
    """
    Tests the matchmaking service with multiple scenarios using parameterization.
    """
    # ARRANGE
    request = MatchmakingRequest(primary_user=primary_user, other_users=[other_user])

    # ACT
    response = get_networking_matches(request)

    # ASSERT
    if expected_score > 0:
        assert len(response.matches) == 1
        assert response.matches[0].match_score == expected_score
        assert sorted(response.matches[0].common_interests) == sorted(expected_common)
    else:
        assert len(response.matches) == 0
