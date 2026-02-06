# app/features/networking/router.py
from fastapi import APIRouter
from .schemas import (
    MatchmakingRequest,
    MatchmakingResponse,
    ConversationStarterRequest,
    ConversationStarterResponse,
    BoothSuggestionRequest,
    BoothSuggestionResponse,
    FollowUpGenerateRequest,
    FollowUpGenerateResponse,
)
from . import service

router = APIRouter()


@router.post(
    "/networking/matchmaking",
    response_model=MatchmakingResponse,
    tags=["AI-Powered Networking & Matchmaking"],
)
async def get_matches(request: MatchmakingRequest):
    """
    Provides AI-powered attendee matching for networking.
    Uses Claude LLM for intelligent matching with algorithmic fallback.
    """
    return await service.get_networking_matches(request)


@router.post(
    "/networking/conversation-starters",
    response_model=ConversationStarterResponse,
    tags=["AI-Powered Networking & Matchmaking"],
)
async def generate_conversation_starters(request: ConversationStarterRequest):
    """Generates AI ice-breaker suggestions for networking. Uses Claude LLM with template fallback."""
    return await service.get_conversation_starters(request)


@router.post(
    "/networking/booth-suggestions",
    response_model=BoothSuggestionResponse,
    tags=["AI-Powered Networking & Matchmaking"],
)
def generate_booth_suggestions(request: BoothSuggestionRequest):
    """Suggests relevant exhibitor booths for attendees."""
    return service.get_booth_suggestions(request)


@router.post(
    "/networking/follow-up/generate",
    response_model=FollowUpGenerateResponse,
    tags=["AI-Powered Networking & Matchmaking"],
)
def generate_follow_up(request: FollowUpGenerateRequest):
    """
    Generate AI-powered follow-up message suggestions.

    Takes connection context (shared sessions, interests, initial messages)
    and generates personalized follow-up messages with appropriate tone.
    """
    return service.generate_follow_up_suggestion(request)
