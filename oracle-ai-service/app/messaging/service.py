import uuid
import random
from datetime import datetime, timezone
from app.schemas.messaging import *


def process_user_interaction(
    interaction: UserInteractionPayload,
) -> EngagementPredictionPayload:
    """Simulates processing a user interaction to generate an engagement prediction."""
    print(
        f"Processing interaction {interaction.interactionId} for user {interaction.userId}..."
    )
    return EngagementPredictionPayload(
        eventId=interaction.eventId,
        sessionId=interaction.sessionId,
        engagementScore=round(random.uniform(70.0, 95.0), 2),
        trend="increasing",
        timestamp=datetime.now(timezone.utc),
    )


def process_attendance_update(
    update: AttendanceUpdatePayload,
) -> CapacityForecastPredictionPayload:
    """Simulates processing attendance data to generate a capacity forecast."""
    print(f"Processing attendance update for session {update.sessionId}...")
    return CapacityForecastPredictionPayload(
        eventId=update.eventId,
        sessionId=update.sessionId,
        forecastedAttendance=int(update.currentAttendance * 1.1),  # Predict 10% more
        overflowProbability=round(random.uniform(0.1, 0.4), 2),
        alertLevel="yellow",
        suggestion="Monitor attendance closely.",
        timestamp=datetime.now(timezone.utc),
    )


def process_session_feedback(feedback: SessionFeedbackPayload) -> SuccessInsightPayload:
    """Simulates processing session feedback to generate a success insight."""
    print(f"Processing feedback for session {feedback.sessionId}...")
    return SuccessInsightPayload(
        insightId=f"ins_{uuid.uuid4().hex[:8]}",
        eventId=feedback.eventId,
        title="Positive Session Feedback Correlates with High Engagement",
        description=f"Session {feedback.sessionId} received a high rating of {feedback.rating}/5, aligning with its high engagement score.",
        severity="info",
        data={"rating": feedback.rating, "sessionId": feedback.sessionId},
        timestamp=datetime.now(timezone.utc),
    )


def process_network_connection(
    connection: NetworkConnectionPayload,
) -> NetworkingSuggestionPayload:
    """Simulates processing a network connection to generate new suggestions."""
    print(
        f"Processing new connection between {connection.user1_id} and {connection.user2_id}..."
    )
    # This would suggest a new person for user1 to meet
    return NetworkingSuggestionPayload(
        suggestionId=f"sug_{uuid.uuid4().hex[:8]}",
        eventId=connection.eventId,
        recipientUserId=connection.user1_id,
        suggestedUserId=f"usr_{random.randint(1000, 9999)}",
        matchScore=round(random.uniform(0.7, 0.9), 2),
        matchReasons=["Shared interest in AI", "Both attended the keynote"],
        suggestedIceBreaker="I saw you also connected with Jane Doe. What are your thoughts on the keynote?",
        timestamp=datetime.now(timezone.utc),
    )
