# app/agents/profile_enrichment/tools/github_api.py
"""
GitHub public API integration with caching and rate limiting.
Uses unauthenticated API for public profile data.
"""

import json
import logging
from typing import Any, Optional

import httpx
import redis.asyncio as aioredis

from app.core.config import settings
from app.core.circuit_breaker import get_github_breaker
from app.core.exceptions import CircuitBreakerOpenError, GitHubAPIError
from app.core.rate_limiter import get_github_limiter

logger = logging.getLogger(__name__)


class GitHubProfileFetcher:
    """
    GitHub profile fetcher with caching and rate limiting.

    Features:
    - 7-day cache for profile data
    - Token bucket rate limiting
    - Circuit breaker for graceful degradation
    - Optional authentication for higher rate limits
    """

    BASE_URL = "https://api.github.com"

    def __init__(
        self,
        redis_client: Optional[aioredis.Redis] = None,
    ):
        """
        Initialize GitHub fetcher.

        Args:
            redis_client: Optional Redis client for caching
        """
        self.redis_client = redis_client
        self._http_client: Optional[httpx.AsyncClient] = None

    async def _get_http_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client with connection pooling."""
        if self._http_client is None or self._http_client.is_closed:
            headers = {
                "Accept": "application/vnd.github.v3+json",
                "User-Agent": "GlobalConnect-Profile-Enrichment",
            }

            # Add auth token if available (increases rate limit)
            if settings.GITHUB_PUBLIC_API_TOKEN:
                headers["Authorization"] = f"token {settings.GITHUB_PUBLIC_API_TOKEN}"

            self._http_client = httpx.AsyncClient(
                base_url=self.BASE_URL,
                headers=headers,
                timeout=30.0,
                limits=httpx.Limits(max_connections=10),
            )

        return self._http_client

    def _cache_key(self, username: str) -> str:
        """Generate cache key for GitHub username."""
        return f"github:profile:{username.lower()}"

    async def _get_cached(self, cache_key: str) -> Optional[dict[str, Any]]:
        """Get cached profile data."""
        if not self.redis_client:
            return None

        try:
            cached = await self.redis_client.get(cache_key)
            if cached:
                logger.debug(f"Cache hit for {cache_key}")
                return json.loads(cached)
        except Exception as e:
            logger.warning(f"Cache read error: {e}")

        return None

    async def _set_cached(self, cache_key: str, data: dict[str, Any]) -> None:
        """Cache profile data."""
        if not self.redis_client:
            return

        try:
            await self.redis_client.setex(
                cache_key,
                settings.GITHUB_CACHE_TTL_SECONDS,
                json.dumps(data),
            )
            logger.debug(f"Cached profile for {cache_key}")
        except Exception as e:
            logger.warning(f"Cache write error: {e}")

    async def fetch_profile(self, username: str) -> Optional[dict[str, Any]]:
        """
        Fetch GitHub profile data for a username.

        Args:
            username: GitHub username

        Returns:
            Profile data dict or None if not found

        Raises:
            GitHubAPIError: If API returns error (except 404)
            CircuitBreakerOpenError: If circuit is open
        """
        # Sanitize username
        username = username.strip().lower()
        if not username:
            return None

        # Check cache first
        cache_key = self._cache_key(username)
        cached = await self._get_cached(cache_key)
        if cached:
            return cached

        # Acquire rate limit token
        limiter = await get_github_limiter()
        await limiter.acquire()

        # Execute with circuit breaker
        breaker = get_github_breaker()

        try:
            async with breaker:
                client = await self._get_http_client()

                # Fetch user profile
                user_response = await client.get(f"/users/{username}")

                if user_response.status_code == 404:
                    logger.debug(f"GitHub user not found: {username}")
                    return None

                if user_response.status_code == 403:
                    # Rate limited
                    logger.warning(f"GitHub rate limit hit for {username}")
                    raise GitHubAPIError(
                        status_code=403,
                        message="GitHub API rate limit exceeded",
                    )

                if user_response.status_code != 200:
                    raise GitHubAPIError(
                        status_code=user_response.status_code,
                        message=f"GitHub API error: {user_response.text}",
                    )

                user_data = user_response.json()

                # Fetch top repositories
                repos_response = await client.get(
                    f"/users/{username}/repos",
                    params={"sort": "updated", "per_page": 10},
                )

                repos = []
                if repos_response.status_code == 200:
                    repos = repos_response.json()

                # Extract languages from repos
                languages: dict[str, int] = {}
                for repo in repos:
                    if repo.get("language"):
                        lang = repo["language"]
                        languages[lang] = languages.get(lang, 0) + 1

                # Sort by frequency
                top_languages = sorted(
                    languages.keys(),
                    key=lambda x: languages[x],
                    reverse=True,
                )[:5]

                # Build profile data
                profile_data = {
                    "username": username,
                    "url": f"https://github.com/{username}",
                    "bio": user_data.get("bio"),
                    "name": user_data.get("name"),
                    "company": user_data.get("company"),
                    "location": user_data.get("location"),
                    "public_repos": user_data.get("public_repos", 0),
                    "followers": user_data.get("followers", 0),
                    "following": user_data.get("following", 0),
                    "top_languages": top_languages,
                    "recent_repos": [repo["name"] for repo in repos[:5]],
                    "hireable": user_data.get("hireable"),
                    "blog": user_data.get("blog"),
                    "twitter_username": user_data.get("twitter_username"),
                }

                # Cache the result
                await self._set_cached(cache_key, profile_data)

                logger.info(f"Fetched GitHub profile for {username}")

                return profile_data

        except CircuitBreakerOpenError:
            raise
        except GitHubAPIError:
            raise
        except Exception as e:
            logger.error(f"GitHub API error for {username}: {e}")
            raise GitHubAPIError(message=str(e))

    async def close(self) -> None:
        """Close HTTP client."""
        if self._http_client and not self._http_client.is_closed:
            await self._http_client.aclose()


# ===========================================
# Module-level convenience functions
# ===========================================

_fetcher: Optional[GitHubProfileFetcher] = None


async def get_github_fetcher() -> GitHubProfileFetcher:
    """Get or create GitHub fetcher singleton."""
    global _fetcher
    if _fetcher is None:
        try:
            redis_client = await aioredis.from_url(
                settings.REDIS_URL,
                encoding="utf-8",
                decode_responses=True,
            )
        except Exception as e:
            logger.warning(f"Could not connect to Redis: {e}")
            redis_client = None

        _fetcher = GitHubProfileFetcher(redis_client=redis_client)

    return _fetcher


async def fetch_github_profile(username: str) -> Optional[dict[str, Any]]:
    """
    Convenience function to fetch GitHub profile.

    Args:
        username: GitHub username

    Returns:
        Profile data dict or None if not found
    """
    fetcher = await get_github_fetcher()
    return await fetcher.fetch_profile(username)
