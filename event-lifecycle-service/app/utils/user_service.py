# app/utils/user_service.py
"""
User service client for fetching user information.

This module provides functions to query user data from the user service.
Uses direct HTTP calls to user-and-org-service internal API.
"""
import logging
import httpx
from typing import Optional, Dict, List
from functools import lru_cache
import asyncio
from app.core.config import settings

logger = logging.getLogger(__name__)

# Cache for user info to reduce API calls
_user_cache: Dict[str, Dict] = {}
_cache_ttl = 300  # 5 minutes


async def get_user_info_async(user_id: str) -> Optional[Dict]:
    """
    Fetch user information asynchronously from the user service.

    Args:
        user_id: The user's ID

    Returns:
        Dict with user info (id, email, firstName, lastName, imageUrl) or None if not found
    """
    # Check cache first
    if user_id in _user_cache:
        return _user_cache[user_id]

    try:
        # Get internal API URL and key from settings
        user_service_url = getattr(settings, 'USER_SERVICE_URL', 'http://user-and-org-service:3000')
        # Strip /graphql suffix if present (common misconfiguration)
        if user_service_url.endswith('/graphql'):
            user_service_url = user_service_url[:-8]
        user_service_url = user_service_url.rstrip('/')
        internal_api_key = getattr(settings, 'INTERNAL_API_KEY', '')

        if not internal_api_key:
            logger.warning(
                f"INTERNAL_API_KEY not configured. Cannot fetch user info for {user_id}"
            )
            return _get_placeholder_user(user_id)

        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(
                f"{user_service_url}/internal/users/{user_id}",
                headers={"x-api-key": internal_api_key}
            )

            if response.status_code == 200:
                user_data = response.json()
                user_info = {
                    "id": user_data.get("id", user_id),
                    "email": user_data.get("email", ""),
                    "firstName": user_data.get("firstName", ""),
                    "lastName": user_data.get("lastName", ""),
                    "imageUrl": user_data.get("imageUrl"),
                    "name": f"{user_data.get('firstName', '')} {user_data.get('lastName', '')}".strip() or "User",
                }
                # Cache the result
                _user_cache[user_id] = user_info
                return user_info
            elif response.status_code == 404:
                logger.warning(f"User {user_id} not found in user service")
                return _get_placeholder_user(user_id)
            else:
                logger.error(
                    f"Failed to fetch user {user_id}: HTTP {response.status_code}"
                )
                return _get_placeholder_user(user_id)

    except httpx.TimeoutException:
        logger.error(f"Timeout fetching user info for {user_id}")
        return _get_placeholder_user(user_id)
    except Exception as e:
        logger.error(f"Error fetching user info for {user_id}: {e}")
        return _get_placeholder_user(user_id)


def _get_placeholder_user(user_id: str) -> Dict:
    """Return a placeholder user when real data isn't available"""
    return {
        "id": user_id,
        "email": "",
        "firstName": "User",
        "lastName": user_id[:8] if len(user_id) > 8 else user_id,
        "imageUrl": None,
        "name": f"User {user_id[:8]}...",
    }


async def get_users_info_batch(user_ids: List[str]) -> Dict[str, Dict]:
    """
    Fetch multiple users' info in parallel.

    Args:
        user_ids: List of user IDs to fetch

    Returns:
        Dict mapping user_id to user info
    """
    if not user_ids:
        return {}

    # Deduplicate
    unique_ids = list(set(user_ids))

    # Fetch in parallel with concurrency limit
    semaphore = asyncio.Semaphore(10)

    async def fetch_with_semaphore(uid: str):
        async with semaphore:
            return uid, await get_user_info_async(uid)

    results = await asyncio.gather(
        *[fetch_with_semaphore(uid) for uid in unique_ids]
    )

    return {uid: info for uid, info in results if info}


def get_user_email_from_token(token_payload) -> Optional[str]:
    """
    Extract user email from JWT token if available.

    Args:
        token_payload: The decoded JWT token payload (TokenPayload object)

    Returns:
        Email address if available in token, None otherwise

    Note: The current JWT token doesn't include email.
    This is a placeholder for when email is added to the token.
    """
    # Check if token has email field (currently it doesn't)
    if hasattr(token_payload, 'email'):
        return token_payload.email

    return None


async def get_user_email(user_id: str, token_payload=None) -> Optional[str]:
    """
    Get user's email address from various sources.

    Tries in order:
    1. JWT token (if email is included)
    2. User service API call
    3. Returns None if not available

    Args:
        user_id: The user's ID
        token_payload: Optional JWT token payload

    Returns:
        Email address or None
    """
    # Try token first (fastest)
    if token_payload:
        email = get_user_email_from_token(token_payload)
        if email:
            return email

    # Try user service
    user_info = await get_user_info_async(user_id)
    if user_info and user_info.get("email"):
        return user_info["email"]

    logger.warning(
        f"Could not fetch email for user {user_id}. "
        "User service integration needed for production."
    )
    return None


async def get_user_name(user_id: str, token_payload=None) -> str:
    """
    Get user's name from user service.

    Args:
        user_id: The user's ID
        token_payload: Optional JWT token payload

    Returns:
        User's name or "User" as fallback
    """
    user_info = await get_user_info_async(user_id)
    if user_info and user_info.get("name"):
        return user_info["name"]

    # Fallback to generic name
    return "User"
