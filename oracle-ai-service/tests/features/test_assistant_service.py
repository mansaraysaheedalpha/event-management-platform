# tests/features/test_assistant_service.py

import pytest
from datetime import time
from app.features.assistant.service import *
from app.features.assistant.schemas import *


@pytest.mark.parametrize(
    "query, expected_response_type, expected_action_name",
    [
        # Test Case 1: Intent is to find a location
        ("Where is the keynote room?", "action", "show_map_route"),
        # Test Case 2: Intent is to get a recommendation
        (
            "Can you recommend a session for me?",
            "action",
            "navigate_to_recommendations",
        ),
        # Test Case 3: Intent is unknown
        ("What's the weather like?", "text", None),
    ],
)
def test_get_concierge_response_recognizes_intents(
    query, expected_response_type, expected_action_name
):
    """
    Tests that the concierge can recognize different user intents from a
    natural language query and return the appropriate response type and action.
    """
    # 1. Arrange
    request = ConciergeRequest(user_id="u1", query=query)

    # 2. Act
    response = get_concierge_response(request)

    # 3. Assert
    assert response.response_type == expected_response_type

    if expected_action_name:
        assert len(response.actions) == 1
        assert response.actions[0].action == expected_action_name
    else:
        assert len(response.actions) == 0


@pytest.mark.parametrize(
    "user_id, persona, expected_time_range",
    [
        ("user_1", "Early Bird", (time(8, 0), time(10, 0))),
        ("user_2", "Business Hours", (time(13, 0), time(16, 0))),
        ("user_3", "Night Owl", (time(20, 0), time(22, 0))),
        ("user_4", "Unknown", (time(9, 0), time(17, 0))),  # Default fallback
    ],
)
def test_get_smart_notification_timing_for_personas(
    mocker, user_id, persona, expected_time_range
):
    """
    Tests that the smart notification service suggests appropriate times
    based on the user's assigned persona.
    """
    # 1. Arrange
    request = SmartNotificationRequest(user_id=user_id, message="Test notification")
    # Mock the helper function that would fetch user data from a database
    mocker.patch(
        "app.features.assistant.service._get_user_persona_from_db", return_value=persona
    )

    # 2. Act
    response = get_smart_notification_timing(request)

    # 3. Assert
    # Check that the recommended time falls within the expected window for the persona
    assert (
        expected_time_range[0]
        <= response.recommended_time.time()
        <= expected_time_range[1]
    )
    assert 0.0 <= response.confidence <= 1.0
