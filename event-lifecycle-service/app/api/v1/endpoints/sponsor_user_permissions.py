# app/api/v1/endpoints/sponsor_user_permissions.py
"""
Admin endpoints for managing sponsor user permissions.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import Any

from app.api import deps
from app.schemas.user import TokenPayload
from app.crud import sponsor_user
from app.core.sponsor_roles import apply_role_permissions

router = APIRouter()


@router.post("/fix-my-permissions")
def fix_my_sponsor_permissions(
    sponsor_id: str,
    *,
    db: Session = Depends(deps.get_db),
    current_user: TokenPayload = Depends(deps.get_current_user),
) -> Any:
    """
    Fix permissions for the current user based on their assigned role.

    This endpoint applies the correct permissions based on the user's role:
    - Admin: Full access to all features
    - Representative: Can view, export, message leads and manage booth
    - Booth Staff: Can view leads and manage booth
    - Viewer: Read-only access to leads

    This is useful for fixing permissions that were incorrectly set when
    invitations were sent before role-based permissions were implemented.
    """
    # Check if user is associated with this sponsor
    su = sponsor_user.get_by_user_and_sponsor(
        db, user_id=current_user.sub, sponsor_id=sponsor_id
    )

    if not su:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="You are not associated with this sponsor"
        )

    # Get permissions for the user's current role
    try:
        role_permissions = apply_role_permissions(su.role)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

    # Apply role-based permissions
    old_permissions = {
        "can_message_attendees": su.can_message_attendees,
        "can_view_leads": su.can_view_leads,
        "can_export_leads": su.can_export_leads,
        "can_manage_booth": su.can_manage_booth,
        "can_invite_others": su.can_invite_others,
    }

    su.can_message_attendees = role_permissions["can_message_attendees"]
    su.can_view_leads = role_permissions["can_view_leads"]
    su.can_export_leads = role_permissions["can_export_leads"]
    su.can_manage_booth = role_permissions["can_manage_booth"]
    su.can_invite_others = role_permissions["can_invite_others"]
    su.is_active = True

    db.commit()
    db.refresh(su)

    return {
        "message": f"Permissions updated successfully based on '{su.role}' role",
        "role": su.role,
        "old_permissions": old_permissions,
        "new_permissions": {
            "can_message_attendees": su.can_message_attendees,
            "can_view_leads": su.can_view_leads,
            "can_export_leads": su.can_export_leads,
            "can_manage_booth": su.can_manage_booth,
            "can_invite_others": su.can_invite_others,
        }
    }
