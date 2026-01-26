# app/api/v1/endpoints/sponsor_user_permissions.py
"""
Admin endpoints for managing sponsor user permissions.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import Any

from app.api.dependencies import get_db, get_current_user
from app.schemas.user import JwtUser
from app.crud import sponsor_user

router = APIRouter()


@router.post("/enable-my-permissions")
def enable_my_sponsor_permissions(
    sponsor_id: str,
    *,
    db: Session = Depends(get_db),
    current_user: JwtUser = Depends(get_current_user),
) -> Any:
    """
    Enable all permissions for the current user on a sponsor.

    This is a temporary endpoint for testing. In production, permissions
    should be managed by sponsor admins through a proper UI.
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

    # Enable all permissions
    su.can_message_attendees = True
    su.can_view_leads = True
    su.can_export_leads = True
    su.can_manage_booth = True
    su.can_invite_others = True
    su.role = "admin"
    su.is_active = True

    db.commit()
    db.refresh(su)

    return {
        "message": "All permissions enabled successfully",
        "permissions": {
            "can_message_attendees": su.can_message_attendees,
            "can_view_leads": su.can_view_leads,
            "can_export_leads": su.can_export_leads,
            "can_manage_booth": su.can_manage_booth,
            "can_invite_others": su.can_invite_others,
            "role": su.role,
        }
    }
