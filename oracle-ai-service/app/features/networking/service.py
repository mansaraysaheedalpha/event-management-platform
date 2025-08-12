import random
import uuid
from app.features.networking.schemas import (
    MatchmakingRequest,
    MatchmakingResponse,
    ConversationStarterRequest,
    ConversationStarterResponse,
    BoothSuggestionRequest,
    BoothSuggestionResponse,
)


import random
from .schemas import MatchmakingRequest, MatchmakingResponse


def get_networking_matches(request: MatchmakingRequest) -> MatchmakingResponse:
    """
    Calculates networking matches based on shared interests.
    This uses a simple Jaccard Index for scoring.
    """
    matches = []
    primary_user_interests = set(request.primary_user.interests)

    for other_user in request.other_users:
        # Do not match a user with themselves
        if request.primary_user.user_id == other_user.user_id:
            continue

        other_user_interests = set(other_user.interests)

        # Calculate the intersection (shared interests)
        common_interests = list(
            primary_user_interests.intersection(other_user_interests)
        )

        # Calculate the union (all unique interests between both)
        union_interests = primary_user_interests.union(other_user_interests)

        # Calculate Jaccard similarity score (intersection / union)
        match_score = (
            len(common_interests) / len(union_interests) if union_interests else 0
        )

        if match_score > 0:
            matches.append(
                MatchmakingResponse.Match(
                    user_id=other_user.user_id,
                    match_score=round(match_score, 2),
                    common_interests=common_interests,
                    match_reasons=[
                        f"You share {len(common_interests)} common interests."
                    ],
                )
            )

    # Sort matches by the highest score
    matches.sort(key=lambda x: x.match_score, reverse=True)

    return MatchmakingResponse(matches=matches[: request.max_matches])


def get_conversation_starters(
    request: ConversationStarterRequest,
) -> ConversationStarterResponse:
    """Simulates generating AI-powered conversation starters."""
    starters = [
        f"I see you're both interested in {request.common_interests[0]}. What's the most exciting development you've seen in that area recently?",
        "What was your key takeaway from the morning keynote?",
    ]
    return ConversationStarterResponse(conversation_starters=starters)


def get_booth_suggestions(request: BoothSuggestionRequest) -> BoothSuggestionResponse:
    """Simulates suggesting relevant exhibitor booths for an attendee."""
    suggestions = [
        BoothSuggestionResponse.SuggestedBooth(
            booth_id="booth_cloudcorp",
            exhibitor_name="CloudCorp Solutions",
            relevance_score=0.92,
        ),
        BoothSuggestionResponse.SuggestedBooth(
            booth_id="booth_innovateai",
            exhibitor_name="InnovateAI",
            relevance_score=0.85,
        ),
    ]
    return BoothSuggestionResponse(suggested_booths=suggestions)
