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


# Sprint 7: Follow-up Message Generation
class FollowUpGenerateRequest(BaseModel):
    """Request for AI-powered follow-up message generation."""

    model_config = {"populate_by_name": True}

    connection_id: str = Field(
        ..., description="The connection ID for context", alias="connectionId"
    )
    user_id: str = Field(
        ..., description="The user requesting the follow-up", alias="userId"
    )
    other_user_name: str = Field(
        ..., description="Name of the person they're following up with", alias="otherUserName"
    )
    other_user_headline: Optional[str] = Field(
        None, description="Professional headline of the other user", alias="otherUserHeadline"
    )
    connection_type: str = Field(
        default="EVENT_NETWORKING", description="How they connected", alias="connectionType"
    )
    contexts: List[dict] = Field(
        default_factory=list,
        description="List of connection contexts, e.g., [{'type': 'SHARED_SESSION', 'value': 'AI Workshop'}]",
    )
    initial_message: Optional[str] = Field(
        None, description="Initial message exchanged when connecting", alias="initialMessage"
    )
    activities: List[dict] = Field(
        default_factory=list,
        description="Recent activities between users",
    )
    tone: str = Field(
        default="professional",
        description="Message tone: professional, casual, or friendly",
    )
    additional_context: Optional[str] = Field(
        None, description="Any additional context the user wants to include", alias="additionalContext"
    )


class FollowUpGenerateResponse(BaseModel):
    """AI-generated follow-up message suggestion."""

    model_config = {"populate_by_name": True}

    suggested_subject: str = Field(
        ..., description="Suggested email subject line", serialization_alias="suggestedSubject"
    )
    suggested_message: str = Field(
        ..., description="The suggested follow-up message", serialization_alias="suggestedMessage"
    )
    talking_points: List[str] = Field(
        default_factory=list, description="Key talking points to include", serialization_alias="talkingPoints"
    )
    context_used: List[str] = Field(
        default_factory=list, description="Contexts that informed the message", serialization_alias="contextUsed"
    )
