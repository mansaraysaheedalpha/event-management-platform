# app/agents/profile_enrichment/tools/tavily_search.py
"""
Tavily search integration with caching and rate limiting.
Searches for public profiles across social platforms.
"""

import hashlib
import json
import logging
from typing import Any, Optional

import httpx
import redis.asyncio as aioredis
from tavily import AsyncTavilyClient

from app.core.config import settings
from app.core.circuit_breaker import get_tavily_breaker
from app.core.exceptions import (
    CircuitBreakerOpenError,
    EnrichmentDisabledError,
    TavilyAPIError,
)
from app.core.rate_limiter import get_tavily_limiter

logger = logging.getLogger(__name__)


class TavilySearchClient:
    """
    Tavily search client with caching, rate limiting, and circuit breaker.

    Features:
    - 24-hour cache for search results (reduces API costs)
    - Token bucket rate limiting
    - Circuit breaker for graceful degradation
    """

    # Domains to search for social profiles
    PROFILE_DOMAINS = [
        "linkedin.com",
        "github.com",
        "twitter.com",
        "x.com",
        "youtube.com",
        "instagram.com",
        "facebook.com",
        "medium.com",
        "dev.to",
    ]

    def __init__(
        self,
        redis_client: Optional[aioredis.Redis] = None,
    ):
        """
        Initialize Tavily client.

        Args:
            redis_client: Optional Redis client for caching
        """
        if not settings.TAVILY_API_KEY:
            raise EnrichmentDisabledError()

        self.client = AsyncTavilyClient(api_key=settings.TAVILY_API_KEY)
        self.redis_client = redis_client
        self._http_client: Optional[httpx.AsyncClient] = None

    async def _get_http_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client (connection pooling)."""
        if self._http_client is None or self._http_client.is_closed:
            self._http_client = httpx.AsyncClient(
                timeout=30.0,
                limits=httpx.Limits(max_connections=10),
            )
        return self._http_client

    def _cache_key(self, query: str, domains: list[str]) -> str:
        """Generate cache key for search query."""
        key_data = f"{query}:{','.join(sorted(domains))}"
        key_hash = hashlib.sha256(key_data.encode()).hexdigest()[:16]
        return f"tavily:search:{key_hash}"

    async def _get_cached(self, cache_key: str) -> Optional[dict[str, Any]]:
        """Get cached search results."""
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
        """Cache search results."""
        if not self.redis_client:
            return

        try:
            await self.redis_client.setex(
                cache_key,
                settings.TAVILY_CACHE_TTL_SECONDS,
                json.dumps(data),
            )
            logger.debug(f"Cached results for {cache_key}")
        except Exception as e:
            logger.warning(f"Cache write error: {e}")

    async def search_profiles(
        self,
        name: str,
        company: str,
        role: str,
        max_results: int = 15,
    ) -> list[dict[str, Any]]:
        """
        Search for public profiles using Tavily.

        Args:
            name: Person's name
            company: Company name
            role: Job role/title
            max_results: Maximum number of results to return

        Returns:
            List of search results with url, title, content

        Raises:
            TavilyAPIError: If API call fails
            CircuitBreakerOpenError: If circuit is open
        """
        # Build search query
        query = f"{name} {company} {role}"

        # Check cache first
        cache_key = self._cache_key(query, self.PROFILE_DOMAINS)
        cached = await self._get_cached(cache_key)
        if cached:
            return cached.get("results", [])

        # Acquire rate limit token
        limiter = await get_tavily_limiter()
        await limiter.acquire()

        # Execute with circuit breaker
        breaker = get_tavily_breaker()

        try:
            async with breaker:
                response = await self.client.search(
                    query=query,
                    search_depth="advanced",
                    include_domains=self.PROFILE_DOMAINS,
                    max_results=max_results,
                )

                results = response.get("results", [])

                # Cache the results
                await self._set_cached(cache_key, {"results": results})

                logger.info(
                    f"Tavily search found {len(results)} results for '{name}'"
                )

                return results

        except CircuitBreakerOpenError:
            raise
        except Exception as e:
            logger.error(f"Tavily API error: {e}")
            raise TavilyAPIError(message=str(e))

    async def close(self) -> None:
        """Close HTTP client."""
        if self._http_client and not self._http_client.is_closed:
            await self._http_client.aclose()


# ===========================================
# Module-level convenience function
# ===========================================

_client: Optional[TavilySearchClient] = None


async def get_tavily_client() -> TavilySearchClient:
    """Get or create Tavily client singleton."""
    global _client
    if _client is None:
        try:
            redis_client = await aioredis.from_url(
                settings.REDIS_URL,
                encoding="utf-8",
                decode_responses=True,
            )
        except Exception as e:
            logger.warning(f"Could not connect to Redis: {e}")
            redis_client = None

        _client = TavilySearchClient(redis_client=redis_client)

    return _client


async def search_profiles(
    name: str,
    company: str,
    role: str,
    max_results: int = 15,
) -> list[dict[str, Any]]:
    """
    Convenience function to search for profiles.

    Args:
        name: Person's name
        company: Company name
        role: Job role/title
        max_results: Maximum results to return

    Returns:
        List of search results
    """
    client = await get_tavily_client()
    return await client.search_profiles(name, company, role, max_results)
