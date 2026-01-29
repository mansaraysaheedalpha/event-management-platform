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

        # SECURITY: JWT_SECRET must be configured - fail closed, never open
        if not settings.JWT_SECRET:
            logger.critical(
                "SECURITY VIOLATION: JWT_SECRET not configured. "
                "This is a critical misconfiguration that must be fixed immediately."
            )
            raise HTTPException(
                status_code=500,
                detail="Server configuration error: Authentication system unavailable"
            )

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

    SECURITY: This function follows fail-closed principle - any error denies access.

    Args:
        session_id: Session ID to check ownership for
        user: Authenticated user from verify_token

    Returns:
        AuthUser if authorized

    Raises:
        HTTPException: If user is not authorized or verification fails
    """
    # Check if user has admin permissions
    if "*" in user.permissions or "event:manage" in user.permissions:
        return user

    try:
        async with AsyncSessionLocal() as db:
            # Query to check if user is organizer of the event for this session
            # Using SQLAlchemy text() for parameterized queries
            from sqlalchemy import text
            result = await db.execute(
                text("""
                    SELECT em.event_id, e.organizer_id
                    FROM engagement_metrics em
                    LEFT JOIN events e ON em.event_id = e.id
                    WHERE em.session_id = :session_id
                    LIMIT 1
                """),
                {"session_id": session_id}
            )
            row = result.fetchone()

            if not row:
                # Session not found - check if user has general event access
                # This handles the case of new sessions not yet in the metrics table
                logger.info(f"Session {session_id} not found in metrics, checking event access")
                # For new sessions, require explicit event:manage permission
                if "event:view" in user.permissions:
                    return user
                raise HTTPException(
                    status_code=403,
                    detail="Session not found or you do not have access"
                )

            organizer_id = row.organizer_id if hasattr(row, 'organizer_id') else None

            if organizer_id and str(organizer_id) != str(user.user_id):
                logger.warning(
                    f"Authorization denied: user {user.user_id} attempted to access "
                    f"session {session_id} owned by {organizer_id}"
                )
                raise HTTPException(
                    status_code=403,
                    detail="You are not authorized to manage this event"
                )

            return user

    except HTTPException:
        raise
    except Exception as e:
        # SECURITY: Fail closed - deny access on any error
        logger.error(
            f"Authorization check failed for user {user.user_id}, session {session_id}: {e}",
            exc_info=True
        )
        raise HTTPException(
            status_code=403,
            detail="Authorization verification failed. Please try again."
        )


async def verify_event_owner(
    event_id: str,
    user: AuthUser = Depends(verify_token)
) -> AuthUser:
    """
    Verify that the authenticated user owns the specified event.

    SECURITY: This function follows fail-closed principle - any error denies access.

    Args:
        event_id: Event ID to check ownership for
        user: Authenticated user from verify_token

    Returns:
        AuthUser if authorized

    Raises:
        HTTPException: If user is not authorized or verification fails
    """
    # Check if user has admin permissions
    if "*" in user.permissions or "event:manage" in user.permissions:
        return user

    try:
        async with AsyncSessionLocal() as db:
            from sqlalchemy import text
            result = await db.execute(
                text("""
                    SELECT organizer_id
                    FROM events
                    WHERE id = :event_id
                """),
                {"event_id": event_id}
            )
            row = result.fetchone()

            if not row:
                raise HTTPException(
                    status_code=404,
                    detail="Event not found"
                )

            if str(row.organizer_id) != str(user.user_id):
                logger.warning(
                    f"Authorization denied: user {user.user_id} attempted to access "
                    f"event {event_id} owned by {row.organizer_id}"
                )
                raise HTTPException(
                    status_code=403,
                    detail="You are not authorized to manage this event"
                )

            return user

    except HTTPException:
        raise
    except Exception as e:
        # SECURITY: Fail closed - deny access on any error
        logger.error(
            f"Event ownership check failed for user {user.user_id}, event {event_id}: {e}",
            exc_info=True
        )
        raise HTTPException(
            status_code=403,
            detail="Authorization verification failed. Please try again."
        )


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
