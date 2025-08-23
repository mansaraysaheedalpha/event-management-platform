# app/features/networking/schemas.py
from pydantic import BaseModel, Field
from typing import List, Optional


class MatchmakingRequest(BaseModel):

    class UserProfile(BaseModel):
        user_id: str
        interests: List[str]

    # The user for whom we are finding matches
    primary_user: UserProfile
    # A list of other users at the event to compare against
    other_users: List[UserProfile]
    max_matches: int = 10


class MatchmakingResponse(BaseModel):
    class Match(BaseModel):
        user_id: str
        match_score: float = Field(..., ge=0, le=1, json_schema_extra={"example": 0.85})
        common_interests: List[str] = Field(
            ..., json_schema_extra={"example": ["API Design", "Microservices"]}
        )
        match_reasons: List[str] = Field(
            ..., json_schema_extra={"example": ["Shared interest in 'Microservices'."]}
        )

    matches: List[Match]


class ConversationStarterRequest(BaseModel):
    user1_id: str
    user2_id: str
    common_interests: List[str]


class ConversationStarterResponse(BaseModel):
    conversation_starters: List[str]


class BoothSuggestionRequest(BaseModel):
    user_id: str
    event_id: str
    user_interests: List[str]


class BoothSuggestionResponse(BaseModel):
    class SuggestedBooth(BaseModel):
        booth_id: str
        exhibitor_name: str
        relevance_score: float

    suggested_booths: List[SuggestedBooth]
