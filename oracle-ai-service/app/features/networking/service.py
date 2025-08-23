# app/features/networking/service.py
import random
import uuid
from typing import List, Dict, Any
from app.features.networking.schemas import (
    MatchmakingRequest,
    MatchmakingResponse,
    ConversationStarterRequest,
    ConversationStarterResponse,
    BoothSuggestionRequest,
    BoothSuggestionResponse,
)

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
    """
    Generates dynamic and relevant conversation starters using a categorized
    template-based model.
    """
    # A pool of templates categorized by context.
    TEMPLATES = {
        "interest_based": [
            "I noticed you're also interested in {interest}. What's the most exciting thing you've learned about it at this event?",
            "How do you use {interest} in your current role?",
            "What do you think is the next big trend for {interest}?",
        ],
        "general_event": [
            "What was your key takeaway from the morning keynote?",
            "Which session has been your favorite so far, and why?",
            "Aside from the sessions, what's been the most valuable part of the event for you?",
        ],
    }

    starters = []

    # Generate at least one starter based on a shared interest, if available.
    if request.common_interests:
        # Pick a random shared interest and a random template
        interest = random.choice(request.common_interests)
        template = random.choice(TEMPLATES["interest_based"])
        starters.append(template.format(interest=interest))

    # Add a couple of general starters to provide variety.
    # Use random.sample to get unique general starters.
    num_general_starters = 2
    if len(TEMPLATES["general_event"]) >= num_general_starters:
        starters.extend(random.sample(TEMPLATES["general_event"], num_general_starters))

    return ConversationStarterResponse(conversation_starters=starters)


def _get_all_booths_from_db(event_id: str) -> List[Dict[str, Any]]:
    """
    This helper function simulates fetching all exhibitor booths for an event
    from a database. Encapsulating data access makes the main logic cleaner
    and easier to mock in tests.
    """
    # In a real application, this would be:
    # return db.query("SELECT * FROM booths WHERE event_id = :event_id", event_id)
    print(f"Simulating DB query for booths in event: {event_id}")
    return [
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
        {
            "booth_id": "booth_5",
            "name": "DevTools Pro",
            "tags": ["VSCode", "Testing", "DevOps"],
        },
    ]


def get_booth_suggestions(request: BoothSuggestionRequest) -> BoothSuggestionResponse:
    """
    Suggests relevant exhibitor booths using a content-based filtering algorithm.
    """
    all_booths = _get_all_booths_from_db(request.event_id)
    user_interests_set = set(request.user_interests)

    scored_booths = []
    for booth in all_booths:
        booth_tags_set = set(booth.get("tags", []))

        # Calculate score based on the number of common tags
        common_tags = user_interests_set.intersection(booth_tags_set)
        score = len(common_tags)

        if score > 0:
            scored_booths.append(
                {"booth_id": booth["booth_id"], "name": booth["name"], "score": score}
            )

    # Sort booths by score, descending
    scored_booths.sort(key=lambda b: b["score"], reverse=True)

    # Format the final response
    suggestions = [
        BoothSuggestionResponse.SuggestedBooth(
            booth_id=booth["booth_id"],
            exhibitor_name=booth["name"],
            relevance_score=booth["score"],
        )
        for booth in scored_booths
    ]

    return BoothSuggestionResponse(suggested_booths=suggestions)


## Module Complete!
