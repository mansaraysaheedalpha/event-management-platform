# app/agents/profile_enrichment/agent.py
"""
Profile Enrichment Agent using LangGraph.

Orchestrates the profile enrichment workflow:
1. Search for profiles using Tavily
2. Extract data from each platform in parallel
3. Merge and validate results
4. Store enriched profile
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Optional

from langgraph.graph import END, StateGraph

from app.agents.profile_enrichment.schemas import (
    EnrichedProfile,
    EnrichmentInput,
    EnrichmentResult,
    EnrichmentState,
    EnrichmentStatus,
    ProfileTier,
)
from app.agents.profile_enrichment.tools.github_api import fetch_github_profile
from app.agents.profile_enrichment.tools.llm_extractor import extract_profile_data
from app.agents.profile_enrichment.tools.tavily_search import search_profiles
from app.core.exceptions import CircuitBreakerOpenError

logger = logging.getLogger(__name__)


# ===========================================
# Agent Nodes
# ===========================================


async def search_profiles_node(state: dict[str, Any]) -> dict[str, Any]:
    """
    Search for user's public profiles across platforms.

    Node 1: Uses Tavily to find profile URLs.
    """
    logger.info(f"Searching profiles for user {state['user_id']}")

    state["started_at"] = datetime.now(timezone.utc).isoformat()
    state["status"] = EnrichmentStatus.PROCESSING.value

    try:
        results = await search_profiles(
            name=state["name"],
            company=state["company"],
            role=state["role"],
            max_results=15,
        )
        state["search_results"] = results
        logger.info(f"Found {len(results)} search results")

    except CircuitBreakerOpenError:
        logger.warning("Tavily circuit breaker open, skipping search")
        state["search_results"] = []
        state["error"] = "Search service temporarily unavailable"

    except Exception as e:
        logger.error(f"Search error: {e}")
        state["search_results"] = []
        state["error"] = str(e)

    return state


async def parallel_extract_node(state: dict[str, Any]) -> dict[str, Any]:
    """
    Extract profile data from all platforms in parallel.

    Node 2: Runs all extraction tasks concurrently for speed.
    """
    logger.info(f"Extracting profiles for user {state['user_id']}")

    search_results = state.get("search_results", [])

    # Define extraction tasks
    async def extract_linkedin() -> Optional[dict[str, Any]]:
        """Extract LinkedIn data."""
        linkedin_results = [
            r for r in search_results
            if "linkedin.com/in/" in r.get("url", "")
        ]
        if not linkedin_results:
            return None

        result = linkedin_results[0]
        return await extract_profile_data(
            platform="linkedin",
            url=result["url"],
            snippet=result.get("content", ""),
        )

    async def extract_github() -> Optional[dict[str, Any]]:
        """Extract GitHub data using public API."""
        # Check if user provided username directly
        if state.get("github_username"):
            return await fetch_github_profile(state["github_username"])

        # Otherwise look in search results
        github_results = [
            r for r in search_results
            if "github.com/" in r.get("url", "")
            and "/repos" not in r.get("url", "")
            and "/blob/" not in r.get("url", "")
        ]
        if not github_results:
            return None

        # Extract username from URL
        url = github_results[0]["url"]
        username = url.split("github.com/")[-1].split("/")[0].split("?")[0]

        if not username or username in ["topics", "search", "trending", "explore"]:
            return None

        return await fetch_github_profile(username)

    async def extract_twitter() -> Optional[dict[str, Any]]:
        """Extract Twitter data."""
        twitter_results = [
            r for r in search_results
            if "twitter.com/" in r.get("url", "") or "x.com/" in r.get("url", "")
        ]
        if not twitter_results:
            return None

        result = twitter_results[0]
        return await extract_profile_data(
            platform="twitter",
            url=result["url"],
            snippet=result.get("content", ""),
        )

    async def extract_youtube() -> Optional[dict[str, Any]]:
        """Extract YouTube data."""
        youtube_results = [
            r for r in search_results
            if "youtube.com/" in r.get("url", "")
            and (
                "/channel/" in r.get("url", "")
                or "/@" in r.get("url", "")
                or "/c/" in r.get("url", "")
            )
        ]
        if not youtube_results:
            return None

        result = youtube_results[0]
        return await extract_profile_data(
            platform="youtube",
            url=result["url"],
            snippet=result.get("content", ""),
        )

    async def extract_instagram() -> Optional[dict[str, Any]]:
        """Extract Instagram data."""
        instagram_results = [
            r for r in search_results
            if "instagram.com/" in r.get("url", "")
        ]
        if not instagram_results:
            return None

        result = instagram_results[0]
        url = result["url"]
        handle = url.split("instagram.com/")[-1].split("/")[0].split("?")[0]

        return await extract_profile_data(
            platform="instagram",
            url=url,
            snippet=result.get("content", ""),
            handle=handle,
        )

    async def extract_facebook() -> Optional[dict[str, Any]]:
        """Extract Facebook data."""
        facebook_results = [
            r for r in search_results
            if "facebook.com/" in r.get("url", "")
        ]
        if not facebook_results:
            return None

        result = facebook_results[0]
        return await extract_profile_data(
            platform="facebook",
            url=result["url"],
            snippet=result.get("content", ""),
        )

    # Run all extractions in parallel
    results = await asyncio.gather(
        extract_linkedin(),
        extract_github(),
        extract_twitter(),
        extract_youtube(),
        extract_instagram(),
        extract_facebook(),
        return_exceptions=True,  # Don't fail if one platform fails
    )

    # Map results to state
    platform_keys = [
        "linkedin_data",
        "github_data",
        "twitter_data",
        "youtube_data",
        "instagram_data",
        "facebook_data",
    ]

    for i, result in enumerate(results):
        if isinstance(result, Exception):
            logger.warning(f"Extraction failed for {platform_keys[i]}: {result}")
            state[platform_keys[i]] = None
        else:
            state[platform_keys[i]] = result

    return state


async def merge_and_validate_node(state: dict[str, Any]) -> dict[str, Any]:
    """
    Merge all extracted data and validate consistency.

    Node 3: Combines data from all sources into unified profile.
    """
    logger.info(f"Merging profiles for user {state['user_id']}")

    enriched: dict[str, Any] = {
        "sources": [],
        # Professional platforms
        "linkedin_url": None,
        "linkedin_headline": None,
        "github_username": None,
        "github_top_languages": [],
        "github_repo_count": 0,
        "twitter_handle": None,
        "twitter_bio": None,
        # Content/Social platforms
        "youtube_channel_url": None,
        "youtube_channel_name": None,
        "youtube_subscriber_range": None,
        "instagram_handle": None,
        "instagram_bio": None,
        "facebook_profile_url": None,
        # Extracted/Inferred
        "extracted_skills": [],
        "extracted_interests": [],
        "inferred_seniority": None,
        "inferred_function": None,
        "is_content_creator": False,
    }

    # Merge LinkedIn data
    linkedin = state.get("linkedin_data")
    if linkedin and isinstance(linkedin, dict):
        enriched["sources"].append("linkedin")
        enriched["linkedin_url"] = linkedin.get("url")
        enriched["linkedin_headline"] = linkedin.get("headline")
        enriched["inferred_seniority"] = linkedin.get("inferred_seniority")
        enriched["inferred_function"] = linkedin.get("inferred_function")

    # Merge GitHub data
    github = state.get("github_data")
    if github and isinstance(github, dict):
        enriched["sources"].append("github")
        enriched["github_username"] = github.get("username")
        enriched["github_top_languages"] = github.get("top_languages", [])
        enriched["github_repo_count"] = github.get("public_repos", 0)

        # Add languages as skills
        languages = github.get("top_languages", [])
        enriched["extracted_skills"].extend(languages)

    # Merge Twitter data
    twitter = state.get("twitter_data")
    if twitter and isinstance(twitter, dict):
        enriched["sources"].append("twitter")
        enriched["twitter_handle"] = twitter.get("handle")
        enriched["twitter_bio"] = twitter.get("bio_snippet")

        # Add inferred interests
        interests = twitter.get("inferred_interests", [])
        enriched["extracted_interests"].extend(interests)

    # Merge YouTube data
    youtube = state.get("youtube_data")
    if youtube and isinstance(youtube, dict):
        enriched["sources"].append("youtube")
        enriched["youtube_channel_url"] = youtube.get("url")
        enriched["youtube_channel_name"] = youtube.get("channel_name")
        enriched["youtube_subscriber_range"] = youtube.get("subscriber_range")

        if youtube.get("is_content_creator"):
            enriched["is_content_creator"] = True

        # Add content focus as interests
        content_focus = youtube.get("content_focus", [])
        enriched["extracted_interests"].extend(content_focus)

    # Merge Instagram data
    instagram = state.get("instagram_data")
    if instagram and isinstance(instagram, dict):
        enriched["sources"].append("instagram")
        enriched["instagram_handle"] = instagram.get("handle")
        enriched["instagram_bio"] = instagram.get("bio_snippet")

        # Add content themes as interests
        themes = instagram.get("content_themes", [])
        enriched["extracted_interests"].extend(themes)

    # Merge Facebook data
    facebook = state.get("facebook_data")
    if facebook and isinstance(facebook, dict):
        enriched["sources"].append("facebook")
        enriched["facebook_profile_url"] = facebook.get("url")

    # Deduplicate skills and interests
    enriched["extracted_skills"] = list(set(enriched["extracted_skills"]))
    enriched["extracted_interests"] = list(set(enriched["extracted_interests"]))

    state["enriched_profile"] = enriched

    # Set status based on results
    if enriched["sources"]:
        state["status"] = EnrichmentStatus.COMPLETED.value
    else:
        state["status"] = EnrichmentStatus.FAILED.value
        state["error"] = state.get("error") or "No profile data found"

    state["completed_at"] = datetime.now(timezone.utc).isoformat()

    logger.info(
        f"Enrichment completed for user {state['user_id']}: "
        f"found {len(enriched['sources'])} sources"
    )

    return state


# ===========================================
# Agent Graph
# ===========================================


def create_enrichment_agent() -> StateGraph:
    """
    Create the profile enrichment agent graph.

    Flow:
    1. search_profiles -> parallel_extract -> merge_and_validate -> END
    """
    # Define the graph with state schema
    workflow = StateGraph(dict)

    # Add nodes
    workflow.add_node("search_profiles", search_profiles_node)
    workflow.add_node("parallel_extract", parallel_extract_node)
    workflow.add_node("merge_and_validate", merge_and_validate_node)

    # Define edges
    workflow.set_entry_point("search_profiles")
    workflow.add_edge("search_profiles", "parallel_extract")
    workflow.add_edge("parallel_extract", "merge_and_validate")
    workflow.add_edge("merge_and_validate", END)

    return workflow.compile()


# ===========================================
# Public API
# ===========================================


async def run_enrichment(input_data: EnrichmentInput) -> EnrichmentResult:
    """
    Run profile enrichment for a user.

    Args:
        input_data: Validated enrichment input

    Returns:
        Enrichment result with profile data and status
    """
    logger.info(f"Starting enrichment for user {input_data.user_id}")

    # Create initial state
    initial_state = {
        "user_id": input_data.user_id,
        "name": input_data.name,
        "email": input_data.email,
        "company": input_data.company,
        "role": input_data.role,
        "linkedin_url": input_data.linkedin_url,
        "github_username": input_data.github_username,
        "twitter_handle": input_data.twitter_handle,
        "search_results": [],
        "linkedin_data": None,
        "github_data": None,
        "twitter_data": None,
        "youtube_data": None,
        "instagram_data": None,
        "facebook_data": None,
        "enriched_profile": None,
        "status": EnrichmentStatus.PENDING.value,
        "error": None,
        "started_at": None,
        "completed_at": None,
    }

    # Create and run agent
    agent = create_enrichment_agent()

    try:
        final_state = await agent.ainvoke(initial_state)

        # Convert to EnrichmentState for result creation
        state = EnrichmentState(
            user_id=final_state["user_id"],
            name=final_state["name"],
            email=final_state["email"],
            company=final_state["company"],
            role=final_state["role"],
            search_results=final_state.get("search_results", []),
            linkedin_data=final_state.get("linkedin_data"),
            github_data=final_state.get("github_data"),
            twitter_data=final_state.get("twitter_data"),
            youtube_data=final_state.get("youtube_data"),
            instagram_data=final_state.get("instagram_data"),
            facebook_data=final_state.get("facebook_data"),
            enriched_profile=final_state.get("enriched_profile"),
            status=EnrichmentStatus(final_state.get("status", "FAILED")),
            error=final_state.get("error"),
            started_at=(
                datetime.fromisoformat(final_state["started_at"])
                if final_state.get("started_at")
                else None
            ),
            completed_at=(
                datetime.fromisoformat(final_state["completed_at"])
                if final_state.get("completed_at")
                else None
            ),
        )

        return EnrichmentResult.from_state(state)

    except Exception as e:
        logger.error(
            "Enrichment agent error",
            extra={
                "user_id": input_data.user_id,
                "error_type": type(e).__name__,
                "error_message": str(e),
            },
        )
        return EnrichmentResult(
            user_id=input_data.user_id,
            status=EnrichmentStatus.FAILED,
            profile_tier=ProfileTier.TIER_3_MANUAL,
            error=str(e),
            sources_found=[],
            missing_sources=["linkedin", "github", "twitter", "youtube", "instagram", "facebook"],
        )
