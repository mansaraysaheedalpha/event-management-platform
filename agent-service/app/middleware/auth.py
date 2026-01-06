"""
Authentication and Authorization Middleware
"""

from fastapi import Header, HTTPException, Depends
from jose import JWTError, jwt
from typing import Optional
import logging

from app.core.config import get_settings
from app.db.timescale import AsyncSessionLocal

logger = logging.getLogger(__name__)

settings = get_settings()


class AuthUser:
    """Authenticated user information"""
    def __init__(self, user_id: str, email: str, permissions: list[str] = None):
        self.user_id = user_id
        self.email = email
        self.permissions = permissions or []


async def verify_token(authorization: Optional[str] = Header(None)) -> AuthUser:
    """
    Verify JWT token from Authorization header.

    Args:
        authorization: Authorization header (Bearer <token>)

    Returns:
        AuthUser with user information

    Raises:
        HTTPException: If token is invalid or missing
    """
    if not authorization:
        raise HTTPException(
            status_code=401,
            detail="Missing authorization header"
        )

    try:
        # Extract token from "Bearer <token>"
        scheme, token = authorization.split()
        if scheme.lower() != "bearer":
            raise HTTPException(
                status_code=401,
                detail="Invalid authentication scheme. Use Bearer token."
            )

        # Verify JWT token
        if not settings.JWT_SECRET:
            logger.warning("JWT_SECRET not configured - authentication disabled in development")
            # Development mode: Allow without verification
            return AuthUser(user_id="dev_user", email="dev@example.com", permissions=["*"])

        payload = jwt.decode(
            token,
            settings.JWT_SECRET,
            algorithms=["HS256"]
        )

        user_id = payload.get("sub")
        email = payload.get("email")
        permissions = payload.get("permissions", [])

        if not user_id:
            raise HTTPException(
                status_code=401,
                detail="Invalid token payload"
            )

        return AuthUser(user_id=user_id, email=email, permissions=permissions)

    except ValueError:
        raise HTTPException(
            status_code=401,
            detail="Invalid authorization header format"
        )
    except JWTError as e:
        raise HTTPException(
            status_code=401,
            detail=f"Invalid or expired token: {str(e)}"
        )


async def verify_organizer(
    session_id: str,
    user: AuthUser = Depends(verify_token)
) -> AuthUser:
    """
    Verify that the authenticated user is an organizer for the event/session.

    Args:
        session_id: Session ID to check ownership for
        user: Authenticated user from verify_token

    Returns:
        AuthUser if authorized

    Raises:
        HTTPException: If user is not authorized
    """
    # Development bypass
    if user.user_id == "dev_user":
        return user

    # Check if user has admin permissions
    if "*" in user.permissions or "event:manage" in user.permissions:
        return user

    # TODO: Query database to verify user owns the event for this session
    # For now, we'll implement a basic check
    try:
        async with AsyncSessionLocal() as db:
            # Query to check if user is organizer of the event for this session
            result = await db.execute(
                """
                SELECT em.event_id, e.organizer_id
                FROM engagement_metrics em
                LEFT JOIN events e ON em.event_id = e.id
                WHERE em.session_id = :session_id
                LIMIT 1
                """,
                {"session_id": session_id}
            )
            row = result.fetchone()

            if not row:
                # Session not found or no data yet - allow for now
                logger.warning(f"Session {session_id} not found in database")
                return user

            organizer_id = row.organizer_id if hasattr(row, 'organizer_id') else None

            if organizer_id and organizer_id != user.user_id:
                raise HTTPException(
                    status_code=403,
                    detail="You are not authorized to manage this event"
                )

            return user

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error verifying organizer permissions: {e}")
        # Fail open in case of database errors (for now)
        # In production, you might want to fail closed
        return user


async def verify_event_owner(
    event_id: str,
    user: AuthUser = Depends(verify_token)
) -> AuthUser:
    """
    Verify that the authenticated user owns the specified event.

    Args:
        event_id: Event ID to check ownership for
        user: Authenticated user from verify_token

    Returns:
        AuthUser if authorized

    Raises:
        HTTPException: If user is not authorized
    """
    # Development bypass
    if user.user_id == "dev_user":
        return user

    # Check if user has admin permissions
    if "*" in user.permissions or "event:manage" in user.permissions:
        return user

    # TODO: Query main database to verify event ownership
    # This would typically call the event-lifecycle-service or query shared DB
    try:
        async with AsyncSessionLocal() as db:
            # Placeholder query - adjust based on your schema
            result = await db.execute(
                """
                SELECT organizer_id
                FROM events
                WHERE id = :event_id
                """,
                {"event_id": event_id}
            )
            row = result.fetchone()

            if not row:
                raise HTTPException(
                    status_code=404,
                    detail="Event not found"
                )

            if row.organizer_id != user.user_id:
                raise HTTPException(
                    status_code=403,
                    detail="You are not authorized to manage this event"
                )

            return user

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error verifying event ownership: {e}")
        # Fail open for now - in production you may want to fail closed
        return user


def has_permission(user: AuthUser, required_permission: str) -> bool:
    """
    Check if user has a specific permission.

    Args:
        user: Authenticated user
        required_permission: Permission to check (e.g., "agent:manage")

    Returns:
        True if user has permission
    """
    if "*" in user.permissions:
        return True

    return required_permission in user.permissions
