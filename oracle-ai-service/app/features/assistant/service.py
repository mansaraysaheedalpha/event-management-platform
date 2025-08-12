from datetime import datetime, timezone, timedelta
import random
from app.features.assistant.schemas import (
    ConciergeRequest,
    ConciergeResponse,
    SmartNotificationRequest,
    SmartNotificationResponse,
)


def get_smart_notification_timing(
    request: SmartNotificationRequest,
) -> SmartNotificationResponse:
    """Simulates finding the optimal time to send a notification."""
    # Simulate finding a time in the near future
    optimal_time = datetime.now(timezone.utc) + timedelta(minutes=random.randint(5, 60))

    return SmartNotificationResponse(
        recommended_time=optimal_time, confidence=round(random.uniform(0.80, 0.99), 2)
    )


def get_concierge_response(request: ConciergeRequest) -> ConciergeResponse:
    """
    This service function simulates the logic of an AI concierge.
    In a real system, this would connect to a Large Language Model (LLM) or
    a Natural Language Understanding (NLU) service like Dialogflow or Rasa.

    For now, we'll use simple keyword matching to simulate different responses.
    """
    query = request.query.lower()

    # Default response
    response_text = "I'm sorry, I can't help with that right now. You can try asking about session recommendations or directions."
    response_type = "text"
    actions = []
    follow_ups = [
        "What are the most popular sessions?",
        "Where is the main keynote room?",
    ]

    # Keyword-based logic simulation
    if "recommend" in query and "session" in query:
        response_text = "I recommend the 'Advanced Microservice Architecture' session. I can also show you other options."
        response_type = "action"
        actions.append(
            ConciergeResponse.Action(
                action="navigate_to_session",
                parameters={"session_id": f"ses_{random.randint(1000, 9999)}"},
            )
        )
        follow_ups = [
            "Tell me more about that session.",
            "What other sessions are happening now?",
        ]

    elif "where is" in query or "directions" in query:
        response_text = "The main keynote is in Hall A. I've highlighted the route for you on the map."
        response_type = "action"
        actions.append(
            ConciergeResponse.Action(
                action="show_map_route", parameters={"destination": "Hall A"}
            )
        )
        follow_ups = [
            "How long will it take to get there?",
            "What's the capacity of Hall A?",
        ]

    return ConciergeResponse(
        response=response_text,
        response_type=response_type,
        actions=actions,
        follow_up_questions=follow_ups,
    )
