# app/api/v1/endpoints/sponsor_team.py
"""
Sponsor team management endpoints.

Allows sponsor admins to invite and manage their own team members.
"""

from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List, Any

from app.api import deps
from app.schemas.token import TokenPayload
from app.schemas.sponsor import (
    SponsorInvitationCreate,
    SponsorInvitationResponse,
    SponsorUserResponse,
)
from app.crud import sponsor, sponsor_user, sponsor_invitation
from app.utils.sponsor_notifications import send_sponsor_invitation_email
from app.core.sponsor_roles import apply_role_permissions
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get(
    "/{sponsor_id}/team",
    response_model=List[SponsorUserResponse]
)
def list_team_members(
    sponsor_id: str,
    *,
    db: Session = Depends(deps.get_db),
    current_user: TokenPayload = Depends(deps.get_current_user),
) -> Any:
    """
    List all team members for this sponsor.

    Any active sponsor user can view the team.
    """
    # Verify user is associated with this sponsor
    su = sponsor_user.get_by_user_and_sponsor(
        db, user_id=current_user.sub, sponsor_id=sponsor_id
    )

    if not su or not su.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to view this sponsor's team"
        )

    # Get all team members
    team_members = sponsor_user.get_by_sponsor(db, sponsor_id=sponsor_id)

    return team_members


@router.post(
    "/{sponsor_id}/team/invite",
    response_model=SponsorInvitationResponse,
    status_code=status.HTTP_201_CREATED
)
def invite_team_member(
    sponsor_id: str,
    invitation_in: SponsorInvitationCreate,
    background_tasks: BackgroundTasks,
    *,
    db: Session = Depends(deps.get_db),
    current_user: TokenPayload = Depends(deps.get_current_user),
) -> Any:
    """
    Invite a new team member to this sponsor.

    Only users with can_invite_others permission can invite team members.
    Typically this is limited to admins.
    """
    # Verify user has permission to invite others
    su = sponsor_user.get_by_user_and_sponsor(
        db, user_id=current_user.sub, sponsor_id=sponsor_id
    )

    if not su or not su.is_active or not su.can_invite_others:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to invite team members. Only admins can invite others."
        )

    # Get sponsor details
    sponsor_obj = sponsor.get(db, id=sponsor_id)
    if not sponsor_obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Sponsor not found"
        )

    # Check for existing pending invitation
    existing = sponsor_invitation.get_pending_by_email(
        db, email=invitation_in.email, sponsor_id=sponsor_id
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="An invitation is already pending for this email"
        )

    # Check max representatives limit
    if sponsor_obj.tier:
        current_count = sponsor_user.count_by_sponsor(db, sponsor_id=sponsor_id)
        pending_count = len(sponsor_invitation.get_by_sponsor(db, sponsor_id=sponsor_id, status='pending'))

        if current_count + pending_count >= sponsor_obj.tier.max_representatives:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Maximum team members ({sponsor_obj.tier.max_representatives}) reached for your sponsor tier"
            )

    # Apply role-based permissions automatically
    role_permissions = apply_role_permissions(invitation_in.role)

    invitation_in.can_view_leads = role_permissions["can_view_leads"]
    invitation_in.can_export_leads = role_permissions["can_export_leads"]
    invitation_in.can_message_attendees = role_permissions["can_message_attendees"]
    invitation_in.can_manage_booth = role_permissions["can_manage_booth"]
    invitation_in.can_invite_others = role_permissions["can_invite_others"]

    # Create invitation
    invitation = sponsor_invitation.create_invitation(
        db,
        invitation_in=invitation_in,
        sponsor_id=sponsor_id,
        invited_by_user_id=current_user.sub
    )

    # Send invitation email in background
    background_tasks.add_task(
        send_sponsor_invitation_email,
        invitation_email=invitation.email,
        invitation_token=invitation.token,
        sponsor_name=sponsor_obj.company_name,
        inviter_name=current_user.full_name or current_user.email,
        role=invitation.role,
        personal_message=invitation.personal_message
    )

    logger.info(f"Team invitation created by {current_user.sub} for sponsor {sponsor_id}: {invitation.id}")

    return invitation


@router.get(
    "/{sponsor_id}/team/invitations",
    response_model=List[SponsorInvitationResponse]
)
def list_team_invitations(
    sponsor_id: str,
    status_filter: str = None,
    *,
    db: Session = Depends(deps.get_db),
    current_user: TokenPayload = Depends(deps.get_current_user),
) -> Any:
    """
    List all invitations for this sponsor.

    Only users with can_invite_others permission can view invitations.
    """
    # Verify user has permission
    su = sponsor_user.get_by_user_and_sponsor(
        db, user_id=current_user.sub, sponsor_id=sponsor_id
    )

    if not su or not su.is_active or not su.can_invite_others:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to view invitations"
        )

    return sponsor_invitation.get_by_sponsor(
        db, sponsor_id=sponsor_id, status=status_filter
    )


@router.delete(
    "/{sponsor_id}/team/invitations/{invitation_id}",
    status_code=status.HTTP_200_OK
)
def revoke_team_invitation(
    sponsor_id: str,
    invitation_id: str,
    *,
    db: Session = Depends(deps.get_db),
    current_user: TokenPayload = Depends(deps.get_current_user),
) -> Any:
    """
    Revoke a pending invitation.

    Only users with can_invite_others permission can revoke invitations.
    """
    # Verify user has permission
    su = sponsor_user.get_by_user_and_sponsor(
        db, user_id=current_user.sub, sponsor_id=sponsor_id
    )

    if not su or not su.is_active or not su.can_invite_others:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to revoke invitations"
        )

    # Get and verify invitation
    invitation = sponsor_invitation.get(db, id=invitation_id)
    if not invitation or invitation.sponsor_id != sponsor_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invitation not found"
        )

    if invitation.status != "pending":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot revoke invitation with status: {invitation.status}"
        )

    # Revoke invitation
    sponsor_invitation.revoke_invitation(db, invitation_id=invitation_id)

    logger.info(f"Invitation {invitation_id} revoked by {current_user.sub}")

    return {"message": "Invitation revoked successfully"}


@router.delete(
    "/{sponsor_id}/team/{user_id}",
    status_code=status.HTTP_200_OK
)
def remove_team_member(
    sponsor_id: str,
    user_id: str,
    *,
    db: Session = Depends(deps.get_db),
    current_user: TokenPayload = Depends(deps.get_current_user),
) -> Any:
    """
    Remove a team member from this sponsor.

    Only users with can_invite_others permission can remove team members.
    Users cannot remove themselves.
    """
    # Verify user has permission
    su = sponsor_user.get_by_user_and_sponsor(
        db, user_id=current_user.sub, sponsor_id=sponsor_id
    )

    if not su or not su.is_active or not su.can_invite_others:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to remove team members"
        )

    # Cannot remove yourself
    if user_id == current_user.sub:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot remove yourself. Ask another admin to remove you."
        )

    # Get target user
    target_user = sponsor_user.get_by_user_and_sponsor(
        db, user_id=user_id, sponsor_id=sponsor_id
    )

    if not target_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Team member not found"
        )

    # Check if this is the last admin
    all_team = sponsor_user.get_by_sponsor(db, sponsor_id=sponsor_id)
    admin_count = sum(1 for member in all_team if member.can_invite_others and member.is_active)

    if target_user.can_invite_others and admin_count <= 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot remove the last admin. Promote someone else to admin first."
        )

    # Deactivate user (soft delete)
    target_user.is_active = False
    db.commit()

    logger.info(f"Team member {user_id} removed from sponsor {sponsor_id} by {current_user.sub}")

    return {"message": "Team member removed successfully"}
