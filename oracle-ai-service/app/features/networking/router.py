from fastapi import APIRouter
from .schemas import *
from . import service

router = APIRouter()


@router.post(
    "/networking/matchmaking",
    response_model=MatchmakingResponse,
    tags=["AI-Powered Networking & Matchmaking"],
)
def get_matches(request: MatchmakingRequest):
    """
    Provides AI-powered attendee matching for networking.
    """
    return service.get_networking_matches(request)


@router.post(
    "/networking/conversation-starters",
    response_model=ConversationStarterResponse,
    tags=["AI-Powered Networking & Matchmaking"],
)
def generate_conversation_starters(request: ConversationStarterRequest):
    """Generates AI ice-breaker suggestions for networking."""
    return service.get_conversation_starters(request)


@router.post(
    "/networking/booth-suggestions",
    response_model=BoothSuggestionResponse,
    tags=["AI-Powered Networking & Matchmaking"],
)
def generate_booth_suggestions(request: BoothSuggestionRequest):
    """Suggests relevant exhibitor booths for attendees."""
    return service.get_booth_suggestions(request)
