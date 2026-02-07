#app/messaging/service.py
import uuid
import random
import asyncio
from datetime import datetime, timezone
from app.schemas.messaging import *
from app.features.networking.schemas import MatchmakingRequest, UserProfile
from app.features.networking.service import get_networking_matches, get_conversation_starters
from app.features.networking.schemas import ConversationStarterRequest


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


async def process_network_connection(
    connection: NetworkConnectionPayload,
) -> NetworkingSuggestionPayload:
    """
    Processes a network connection to generate new AI-powered suggestions.

    Uses real matchmaking when candidate data is available, otherwise returns
    a placeholder suggestion (to avoid fake user IDs in production).
    """
    print(
        f"[SUGGESTIONS] Processing new connection between {connection.user1_id} and {connection.user2_id}..."
    )

    # If no candidates provided, skip suggestion generation
    # (prevents fake user IDs from being published)
    if not connection.candidates or not connection.user1_profile:
        print(f"[SUGGESTIONS] No candidates provided, skipping suggestion for {connection.user1_id}")
        # Return a minimal payload - the consumer should filter these out
        return NetworkingSuggestionPayload(
            suggestionId=f"sug_{uuid.uuid4().hex[:8]}",
            eventId=connection.eventId,
            recipientUserId=connection.user1_id,
            suggestedUserId="",  # Empty = no real suggestion
            matchScore=0.0,
            matchReasons=[],
            suggestedIceBreaker="",
            timestamp=datetime.now(timezone.utc),
        )

    # Filter out the user they just connected with
    candidates = [
        c for c in connection.candidates
        if c.user_id != connection.user2_id
    ]

    if not candidates:
        print(f"[SUGGESTIONS] No other candidates available for {connection.user1_id}")
        return NetworkingSuggestionPayload(
            suggestionId=f"sug_{uuid.uuid4().hex[:8]}",
            eventId=connection.eventId,
            recipientUserId=connection.user1_id,
            suggestedUserId="",
            matchScore=0.0,
            matchReasons=[],
            suggestedIceBreaker="",
            timestamp=datetime.now(timezone.utc),
        )

    # Convert to matchmaking request format
    primary_user = UserProfile(
        user_id=connection.user1_profile.user_id,
        interests=connection.user1_profile.interests,
        name=connection.user1_profile.name,
        role=connection.user1_profile.role,
        company=connection.user1_profile.company,
        industry=connection.user1_profile.industry,
        goals=connection.user1_profile.goals,
        skills_to_offer=connection.user1_profile.skills_to_offer,
        skills_needed=connection.user1_profile.skills_needed,
        bio=connection.user1_profile.bio,
        headline=connection.user1_profile.headline,
    )

    candidate_profiles = [
        UserProfile(
            user_id=c.user_id,
            interests=c.interests,
            name=c.name,
            role=c.role,
            company=c.company,
            industry=c.industry,
            goals=c.goals,
            skills_to_offer=c.skills_to_offer,
            skills_needed=c.skills_needed,
            bio=c.bio,
            headline=c.headline,
        )
        for c in candidates
    ]

    # Get AI-powered matches
    matchmaking_request = MatchmakingRequest(
        primary_user=primary_user,
        other_users=candidate_profiles,
        max_matches=3,  # Get top 3 suggestions
    )

    matches_response = await get_networking_matches(matchmaking_request)

    if not matches_response.matches:
        print(f"[SUGGESTIONS] No matches found for {connection.user1_id}")
        return NetworkingSuggestionPayload(
            suggestionId=f"sug_{uuid.uuid4().hex[:8]}",
            eventId=connection.eventId,
            recipientUserId=connection.user1_id,
            suggestedUserId="",
            matchScore=0.0,
            matchReasons=[],
            suggestedIceBreaker="",
            timestamp=datetime.now(timezone.utc),
        )

    # Get the top match
    top_match = matches_response.matches[0]
    suggested_candidate = next(
        (c for c in candidates if c.user_id == top_match.user_id), None
    )

    # Generate a personalized ice-breaker
    ice_breaker = "Great to connect! I'd love to hear more about your work."
    if suggested_candidate:
        starter_request = ConversationStarterRequest(
            user1_id=connection.user1_id,
            user2_id=top_match.user_id,
            common_interests=top_match.common_interests,
            user1_name=connection.user1_profile.name,
            user1_role=connection.user1_profile.role,
            user1_company=connection.user1_profile.company,
            user1_bio=connection.user1_profile.bio,
            user2_name=suggested_candidate.name,
            user2_role=suggested_candidate.role,
            user2_company=suggested_candidate.company,
            user2_bio=suggested_candidate.bio,
            match_reasons=top_match.match_reasons,
        )
        try:
            starters_response = await get_conversation_starters(starter_request)
            if starters_response.conversation_starters:
                ice_breaker = starters_response.conversation_starters[0]
        except Exception as e:
            print(f"[SUGGESTIONS] Failed to generate ice-breaker: {e}")

    print(f"[SUGGESTIONS] Generated suggestion for {connection.user1_id} → {top_match.user_id}")

    return NetworkingSuggestionPayload(
        suggestionId=f"sug_{uuid.uuid4().hex[:8]}",
        eventId=connection.eventId,
        recipientUserId=connection.user1_id,
        suggestedUserId=top_match.user_id,
        matchScore=top_match.match_score,
        matchReasons=top_match.match_reasons,
        suggestedIceBreaker=ice_breaker,
        timestamp=datetime.now(timezone.utc),
    )
