# app/agents/profile_enrichment/tools/llm_extractor.py
"""
LLM-based profile data extraction using Anthropic Claude.
Extracts structured data from search result snippets.
"""

import json
import logging
from typing import Any, Optional

from anthropic import AsyncAnthropic

from app.core.config import settings
from app.core.circuit_breaker import get_anthropic_breaker
from app.core.exceptions import AnthropicAPIError, CircuitBreakerOpenError
from app.core.rate_limiter import get_llm_limiter

logger = logging.getLogger(__name__)


class LLMExtractor:
    """
    LLM-based profile data extractor.

    Uses Claude to extract structured information from
    search result snippets when direct API access isn't available.
    """

    MODEL = "claude-3-haiku-20240307"  # Fast and cost-effective for extraction

    def __init__(self):
        """Initialize Anthropic client."""
        if not settings.ANTHROPIC_API_KEY:
            raise ValueError("ANTHROPIC_API_KEY not configured")

        self.client = AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)

    async def extract_linkedin_data(
        self,
        url: str,
        snippet: str,
    ) -> Optional[dict[str, Any]]:
        """
        Extract LinkedIn profile data from search snippet.

        Args:
            url: LinkedIn profile URL
            snippet: Search result snippet/content

        Returns:
            Extracted data dict or None
        """
        prompt = f"""Extract professional information from this LinkedIn search result.

URL: {url}
Snippet: {snippet}

Return a JSON object with these fields (use null for uncertain fields):
{{
    "url": "the LinkedIn profile URL",
    "headline": "their professional headline",
    "inferred_seniority": "junior|mid|senior|executive (based on title/headline)",
    "inferred_function": "engineering|product|design|marketing|sales|operations|leadership|other"
}}

Only include fields you can confidently extract from the snippet."""

        return await self._extract_json(prompt)

    async def extract_twitter_data(
        self,
        url: str,
        snippet: str,
    ) -> Optional[dict[str, Any]]:
        """
        Extract Twitter/X profile data from search snippet.

        Args:
            url: Twitter profile URL
            snippet: Search result snippet

        Returns:
            Extracted data dict or None
        """
        prompt = f"""Extract Twitter profile information from this search result.

URL: {url}
Snippet: {snippet}

Return a JSON object with these fields (use null for uncertain fields):
{{
    "url": "the Twitter profile URL",
    "handle": "@username",
    "bio_snippet": "brief bio if visible",
    "inferred_interests": ["list", "of", "topics", "they", "tweet", "about"]
}}

Only include fields you can confidently extract."""

        return await self._extract_json(prompt)

    async def extract_youtube_data(
        self,
        url: str,
        snippet: str,
    ) -> Optional[dict[str, Any]]:
        """
        Extract YouTube channel data from search snippet.

        Args:
            url: YouTube channel URL
            snippet: Search result snippet

        Returns:
            Extracted data dict or None
        """
        prompt = f"""Extract YouTube channel information from this search result.

URL: {url}
Snippet: {snippet}

Return a JSON object with these fields (use null for uncertain fields):
{{
    "url": "the YouTube channel URL",
    "channel_name": "channel name",
    "subscriber_range": "Under 1K|1K-10K|10K-100K|100K-1M|1M+ (if mentioned)",
    "content_focus": ["list", "of", "content", "topics"],
    "is_content_creator": true or false
}}

Only include fields you can confidently extract."""

        return await self._extract_json(prompt)

    async def extract_instagram_data(
        self,
        url: str,
        handle: str,
        snippet: str,
    ) -> Optional[dict[str, Any]]:
        """
        Extract Instagram profile data from search snippet.

        Args:
            url: Instagram profile URL
            handle: Instagram handle
            snippet: Search result snippet

        Returns:
            Extracted data dict or None
        """
        prompt = f"""Extract Instagram profile information from this search result.

URL: {url}
Handle: @{handle}
Snippet: {snippet}

Return a JSON object with these fields (use null for uncertain fields):
{{
    "url": "the Instagram profile URL",
    "handle": "@username",
    "bio_snippet": "brief bio if visible",
    "is_business_account": true or false (infer from content),
    "content_themes": ["list", "of", "content", "themes"]
}}

Only include fields you can confidently extract."""

        return await self._extract_json(prompt)

    async def extract_facebook_data(
        self,
        url: str,
        snippet: str,
    ) -> Optional[dict[str, Any]]:
        """
        Extract Facebook profile/page data from search snippet.

        Args:
            url: Facebook URL
            snippet: Search result snippet

        Returns:
            Extracted data dict or None
        """
        prompt = f"""Extract Facebook profile/page information from this search result.

URL: {url}
Snippet: {snippet}

Return a JSON object with these fields (use null for uncertain fields):
{{
    "url": "the Facebook URL",
    "profile_type": "personal|business_page|public_figure",
    "name_or_page_title": "name or page title",
    "bio_snippet": "brief description if visible"
}}

Only include fields you can confidently extract."""

        return await self._extract_json(prompt)

    async def _extract_json(self, prompt: str) -> Optional[dict[str, Any]]:
        """
        Make LLM call and extract JSON response.

        Args:
            prompt: Extraction prompt

        Returns:
            Parsed JSON dict or None
        """
        # Acquire rate limit token
        limiter = await get_llm_limiter()
        await limiter.acquire()

        # Execute with circuit breaker
        breaker = get_anthropic_breaker()

        try:
            async with breaker:
                response = await self.client.messages.create(
                    model=self.MODEL,
                    max_tokens=500,
                    messages=[
                        {
                            "role": "user",
                            "content": prompt,
                        }
                    ],
                )

                # Extract text content
                text = response.content[0].text

                # Find JSON in response (may be wrapped in markdown)
                json_str = text
                if "```json" in text:
                    json_str = text.split("```json")[1].split("```")[0]
                elif "```" in text:
                    json_str = text.split("```")[1].split("```")[0]

                # Parse JSON
                try:
                    return json.loads(json_str.strip())
                except json.JSONDecodeError as e:
                    logger.warning(f"Failed to parse LLM JSON response: {e}")
                    return None

        except CircuitBreakerOpenError:
            raise
        except Exception as e:
            logger.error(f"Anthropic API error: {e}")
            raise AnthropicAPIError(message=str(e))


# ===========================================
# Module-level convenience functions
# ===========================================

_extractor: Optional[LLMExtractor] = None


def get_llm_extractor() -> LLMExtractor:
    """Get or create LLM extractor singleton."""
    global _extractor
    if _extractor is None:
        _extractor = LLMExtractor()
    return _extractor


async def extract_profile_data(
    platform: str,
    url: str,
    snippet: str,
    handle: Optional[str] = None,
) -> Optional[dict[str, Any]]:
    """
    Convenience function to extract profile data.

    Args:
        platform: Platform name (linkedin, twitter, youtube, instagram, facebook)
        url: Profile URL
        snippet: Search result snippet
        handle: Optional handle (for Instagram)

    Returns:
        Extracted data dict or None
    """
    extractor = get_llm_extractor()

    if platform == "linkedin":
        return await extractor.extract_linkedin_data(url, snippet)
    elif platform == "twitter":
        return await extractor.extract_twitter_data(url, snippet)
    elif platform == "youtube":
        return await extractor.extract_youtube_data(url, snippet)
    elif platform == "instagram":
        return await extractor.extract_instagram_data(url, handle or "", snippet)
    elif platform == "facebook":
        return await extractor.extract_facebook_data(url, snippet)
    else:
        logger.warning(f"Unknown platform: {platform}")
        return None
