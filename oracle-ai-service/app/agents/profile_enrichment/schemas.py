# app/agents/profile_enrichment/schemas.py
"""
Pydantic schemas for profile enrichment.
All inputs are validated and sanitized to prevent injection attacks.
"""

import re
from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.config import settings


class EnrichmentStatus(str, Enum):
    """Status of profile enrichment."""

    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    OPTED_OUT = "OPTED_OUT"


class ProfileTier(str, Enum):
    """Profile tier based on enrichment quality."""

    TIER_0_PENDING = "TIER_0_PENDING"  # Not yet attempted
    TIER_1_RICH = "TIER_1_RICH"  # Found 3+ sources
    TIER_2_BASIC = "TIER_2_BASIC"  # Found 1-2 sources
    TIER_3_MANUAL = "TIER_3_MANUAL"  # No sources found


class EnrichmentInput(BaseModel):
    """Input for profile enrichment - validated and sanitized."""

    model_config = ConfigDict(str_strip_whitespace=True)

    user_id: str = Field(..., min_length=1, max_length=100)
    name: str = Field(..., min_length=1, max_length=200)
    email: str = Field(..., max_length=320)  # Max email length per RFC
    company: str = Field(..., min_length=1, max_length=200)
    role: str = Field(..., min_length=1, max_length=200)

    # Optional direct profile links (if user provided)
    linkedin_url: Optional[str] = Field(None, max_length=500)
    github_username: Optional[str] = Field(None, max_length=100)
    twitter_handle: Optional[str] = Field(None, max_length=100)

    @field_validator("name", "company", "role")
    @classmethod
    def sanitize_search_input(cls, v: str) -> str:
        """
        Sanitize inputs that will be used in search queries.
        Prevents injection attacks via Tavily search.
        """
        if len(v) > settings.MAX_INPUT_STRING_LENGTH:
            raise ValueError(
                f"Input too long (max {settings.MAX_INPUT_STRING_LENGTH} chars)"
            )

        # Remove potentially dangerous characters for search queries
        # Keep only alphanumeric, spaces, hyphens, periods, and common punctuation
        sanitized = re.sub(r"[^\w\s\-\.\,\'\"@&()]", "", v)

        # Collapse multiple spaces
        sanitized = re.sub(r"\s+", " ", sanitized).strip()

        return sanitized

    @field_validator("linkedin_url")
    @classmethod
    def validate_linkedin_url(cls, v: Optional[str]) -> Optional[str]:
        """Validate LinkedIn URL format."""
        if v is None:
            return None
        if not re.match(r"^https?://(www\.)?linkedin\.com/in/[\w\-]+/?$", v):
            raise ValueError("Invalid LinkedIn profile URL")
        return v

    @field_validator("github_username")
    @classmethod
    def validate_github_username(cls, v: Optional[str]) -> Optional[str]:
        """Validate GitHub username format."""
        if v is None:
            return None
        # GitHub usernames: alphanumeric and hyphens, not starting with hyphen
        if not re.match(r"^[a-zA-Z0-9]([a-zA-Z0-9\-]*[a-zA-Z0-9])?$", v):
            raise ValueError("Invalid GitHub username")
        return v

    @field_validator("twitter_handle")
    @classmethod
    def validate_twitter_handle(cls, v: Optional[str]) -> Optional[str]:
        """Validate Twitter handle format."""
        if v is None:
            return None
        # Remove @ if present
        v = v.lstrip("@")
        if not re.match(r"^[a-zA-Z0-9_]{1,15}$", v):
            raise ValueError("Invalid Twitter handle")
        return v


class LinkedInData(BaseModel):
    """Extracted LinkedIn profile data."""

    url: Optional[str] = None
    headline: Optional[str] = None
    inferred_seniority: Optional[str] = None  # junior|mid|senior|executive
    inferred_function: Optional[str] = None  # engineering|product|design|etc


class GitHubData(BaseModel):
    """Extracted GitHub profile data."""

    username: Optional[str] = None
    url: Optional[str] = None
    bio: Optional[str] = None
    public_repos: int = 0
    followers: int = 0
    top_languages: list[str] = Field(default_factory=list)
    recent_activity: list[str] = Field(default_factory=list)


class TwitterData(BaseModel):
    """Extracted Twitter/X profile data."""

    url: Optional[str] = None
    handle: Optional[str] = None
    bio_snippet: Optional[str] = None
    inferred_interests: list[str] = Field(default_factory=list)


class YouTubeData(BaseModel):
    """Extracted YouTube channel data."""

    url: Optional[str] = None
    channel_name: Optional[str] = None
    subscriber_range: Optional[str] = None  # Under 1K|1K-10K|10K-100K|100K-1M|1M+
    content_focus: list[str] = Field(default_factory=list)
    is_content_creator: bool = False


class InstagramData(BaseModel):
    """Extracted Instagram profile data."""

    url: Optional[str] = None
    handle: Optional[str] = None
    bio_snippet: Optional[str] = None
    is_business_account: bool = False
    content_themes: list[str] = Field(default_factory=list)


class FacebookData(BaseModel):
    """Extracted Facebook profile/page data."""

    url: Optional[str] = None
    profile_type: Optional[str] = None  # personal|business_page|public_figure
    name_or_page_title: Optional[str] = None
    bio_snippet: Optional[str] = None


class EnrichedProfile(BaseModel):
    """Complete enriched profile data."""

    # Sources found
    sources: list[str] = Field(default_factory=list)

    # Professional platforms
    linkedin_url: Optional[str] = None
    linkedin_headline: Optional[str] = None
    github_username: Optional[str] = None
    github_top_languages: list[str] = Field(default_factory=list)
    github_repo_count: int = 0
    twitter_handle: Optional[str] = None
    twitter_bio: Optional[str] = None

    # Content/Social platforms
    youtube_channel_url: Optional[str] = None
    youtube_channel_name: Optional[str] = None
    youtube_subscriber_range: Optional[str] = None
    instagram_handle: Optional[str] = None
    instagram_bio: Optional[str] = None
    facebook_profile_url: Optional[str] = None

    # Extracted/Inferred data
    extracted_skills: list[str] = Field(default_factory=list)
    extracted_interests: list[str] = Field(default_factory=list)
    inferred_seniority: Optional[str] = None
    inferred_function: Optional[str] = None
    is_content_creator: bool = False


class SearchResult(BaseModel):
    """Individual search result from Tavily."""

    url: str
    title: str
    content: str
    score: float = 0.0


class EnrichmentState(BaseModel):
    """State for the enrichment agent (used by LangGraph)."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    # Input
    user_id: str
    name: str
    email: str
    company: str
    role: str

    # Optional direct links
    linkedin_url: Optional[str] = None
    github_username: Optional[str] = None
    twitter_handle: Optional[str] = None

    # Search results
    search_results: list[dict[str, Any]] = Field(default_factory=list)

    # Extracted platform data
    linkedin_data: Optional[dict[str, Any]] = None
    github_data: Optional[dict[str, Any]] = None
    twitter_data: Optional[dict[str, Any]] = None
    youtube_data: Optional[dict[str, Any]] = None
    instagram_data: Optional[dict[str, Any]] = None
    facebook_data: Optional[dict[str, Any]] = None

    # Final output
    enriched_profile: Optional[dict[str, Any]] = None
    status: EnrichmentStatus = EnrichmentStatus.PENDING
    error: Optional[str] = None

    # Processing metadata
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


class EnrichmentResult(BaseModel):
    """Final result of enrichment process."""

    user_id: str
    status: EnrichmentStatus
    profile_tier: ProfileTier
    enriched_profile: Optional[EnrichedProfile] = None
    sources_found: list[str] = Field(default_factory=list)
    missing_sources: list[str] = Field(default_factory=list)
    error: Optional[str] = None
    processing_time_seconds: Optional[float] = None

    @classmethod
    def from_state(cls, state: EnrichmentState) -> "EnrichmentResult":
        """Create result from agent state."""
        sources = []
        if state.enriched_profile:
            sources = state.enriched_profile.get("sources", [])

        all_sources = ["linkedin", "github", "twitter", "youtube", "instagram", "facebook"]
        missing = [s for s in all_sources if s not in sources]

        # Determine tier
        if len(sources) >= 3:
            tier = ProfileTier.TIER_1_RICH
        elif len(sources) >= 1:
            tier = ProfileTier.TIER_2_BASIC
        else:
            tier = ProfileTier.TIER_3_MANUAL

        processing_time = None
        if state.started_at and state.completed_at:
            processing_time = (state.completed_at - state.started_at).total_seconds()

        return cls(
            user_id=state.user_id,
            status=state.status,
            profile_tier=tier,
            enriched_profile=(
                EnrichedProfile(**state.enriched_profile)
                if state.enriched_profile
                else None
            ),
            sources_found=sources,
            missing_sources=missing,
            error=state.error,
            processing_time_seconds=processing_time,
        )
