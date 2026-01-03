# app/utils/user_service.py
"""
User service client for fetching user information.

This module provides functions to query user data from the user service.
Currently uses a placeholder implementation that can be extended to use:
- GraphQL Apollo Gateway
- Direct HTTP calls to user service
- Cached user data
"""
import logging
import httpx
from typing import Optional, Dict
from app.core.config import settings

logger = logging.getLogger(__name__)


async def get_user_info_async(user_id: str) -> Optional[Dict]:
    """
    Fetch user information asynchronously from the user service.

    Args:
        user_id: The user's ID

    Returns:
        Dict with user info (email, name, etc.) or None if not found

    TODO: Implement actual integration with user service via:
    - GraphQL query to Apollo Gateway
    - Or direct HTTP call to user-and-org-service
    """
    # Placeholder implementation
    # In production, this would query the actual user service

    logger.warning(
        f"get_user_info_async called for user {user_id}. "
        "Placeholder implementation - returning None. "
        "Integrate with user service for production use."
    )

    # Example of what the integration might look like:
    # try:
    #     async with httpx.AsyncClient() as client:
    #         # Option 1: GraphQL to Apollo Gateway
    #         query = """
    #         query GetUser($userId: ID!) {
    #             user(id: $userId) {
    #                 id
    #                 email
    #                 name
    #             }
    #         }
    #         """
    #         response = await client.post(
    #             "http://apollo-gateway:4000/graphql",
    #             json={"query": query, "variables": {"userId": user_id}}
    #         )
    #         data = response.json()
    #         user = data.get("data", {}).get("user")
    #
    #         if user:
    #             return {
    #                 "id": user["id"],
    #                 "email": user["email"],
    #                 "name": user.get("name", "User"),
    #             }
    # except Exception as e:
    #     logger.error(f"Failed to fetch user info for {user_id}: {e}")

    return None


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
