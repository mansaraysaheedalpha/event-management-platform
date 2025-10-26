# app/features/assistant/service.py

from datetime import datetime, timezone, timedelta
import random
from .schemas import (
    ConciergeRequest,
    ConciergeResponse,
    SmartNotificationRequest,
    SmartNotificationResponse,
)


def get_concierge_response(request: ConciergeRequest) -> ConciergeResponse:
    """
    Processes a user's natural language query using a basic
    keyword-based intent recognition engine.
    """
    query = request.query.lower()

    # --- Intent Recognition Engine ---

    # Intent 1: Find Location
    if "where is" in query or "directions" in query or "location of" in query:
        return ConciergeResponse(
            response="I can help with that. Here are the directions.",
            response_type="action",
            actions=[
                ConciergeResponse.Action(
                    action="show_map_route",
                    parameters={
                        "destination": "Main Hall"
                    },  # In a real app, you'd parse the destination
                )
            ],
            follow_up_questions=["What is the schedule for the Main Hall?"],
            is_processing=False,  # Response is complete
        )

    # Intent 2: Get Recommendation
    if "recommend" in query or "suggest" in query:
        return ConciergeResponse(
            response="Certainly, here are some personalized session recommendations for you.",
            response_type="action",
            actions=[
                ConciergeResponse.Action(
                    action="navigate_to_recommendations", parameters={}
                )
            ],
            follow_up_questions=["Can you recommend a speaker?"],
            is_processing=False,  # Response is complete
        )

    # Default Fallback Response (Intent Unknown)
    return ConciergeResponse(
        response="I'm sorry, I can only help with event directions and recommendations at the moment.",
        response_type="text",
        actions=[],
        follow_up_questions=[
            "Where is the keynote room?",
            "Can you recommend a session for me?",
        ],
        is_processing=False,  # Response is complete
    )


def _get_user_persona_from_db(user_id: str) -> str:
    """
    Simulates fetching a user's engagement persona from a database.
    In a real system, this would be determined by analyzing historical user activity.
    """
    # This mock logic allows us to test different personas.
    if "early" in user_id:
        return "Early Bird"
    if "night" in user_id:
        return "Night Owl"
    if "business" in user_id:
        return "Business Hours"
    return "Unknown"


def get_smart_notification_timing(
    request: SmartNotificationRequest,
) -> SmartNotificationResponse:
    """
    Recommends an optimal notification time based on the user's persona.
    """
    persona = _get_user_persona_from_db(request.user_id)
    now = datetime.now(timezone.utc)

    # --- Heuristic Persona Model ---
    if persona == "Early Bird":
        # Suggest a time between 8 AM and 10 AM on the same day
        optimal_time = now.replace(hour=9, minute=0, second=0)
        confidence = 0.90
    elif persona == "Night Owl":
        # Suggest a time between 8 PM and 10 PM on the same day
        optimal_time = now.replace(hour=21, minute=0, second=0)
        confidence = 0.88
    elif persona == "Business Hours":
        # Suggest a time between 1 PM and 4 PM on the same day (post-lunch)
        optimal_time = now.replace(hour=14, minute=30, second=0)
        confidence = 0.85
    else:
        # Default fallback for unknown personas
        optimal_time = now.replace(hour=10, minute=0, second=0)
        confidence = 0.70

    # If the calculated optimal time has already passed for today, schedule it for tomorrow
    if optimal_time < now:
        optimal_time += timedelta(days=1)

    return SmartNotificationResponse(
        recommended_time=optimal_time, confidence=confidence
    )
