# app/api/v1/endpoints/sponsors.py
"""
API endpoints for sponsor management.

These endpoints allow organizers to:
- Create and manage sponsor tiers
- Add and manage sponsors for events
- Invite sponsor representatives
- View and manage sponsor leads

And allow sponsor representatives to:
- View their leads
- Export lead data
- Manage their booth
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks, Request
from sqlalchemy.orm import Session
import logging
import httpx

from app.api import deps
from app.db.session import get_db
from app.core.limiter import limiter
from app.core.config import settings
from app.crud.crud_sponsor import (
    sponsor_tier, sponsor, sponsor_user,
    sponsor_invitation, sponsor_lead
)
from app.schemas.sponsor import (
    SponsorTierCreate, SponsorTierUpdate, SponsorTierResponse,
    SponsorCreate, SponsorUpdate, SponsorResponse, SponsorWithTierResponse,
    SponsorUserCreate, SponsorUserUpdate, SponsorUserResponse,
    SponsorInvitationCreate, SponsorInvitationResponse, AcceptInvitationRequest,
    SponsorInvitationPreviewResponse, AcceptInvitationNewUserRequest,
    AcceptInvitationExistingUserRequest, AcceptInvitationResponse,
    SponsorLeadCreate, SponsorLeadResponse, SponsorLeadUpdate, SponsorStats,
    UserSponsorStatusResponse, SponsorSummary, SponsorBoothSettingsUpdate,
    ManualLeadCaptureCreate,
)
from app.schemas.token import TokenPayload
from app.utils.sponsor_notifications import (
    send_sponsor_invitation_email,
    send_lead_notification_email,
    emit_lead_captured_event,
)

router = APIRouter(tags=["Sponsors"])
logger = logging.getLogger(__name__)


# ==================== Sponsor Tier Endpoints ====================

@router.post(
    "/organizations/{org_id}/events/{event_id}/sponsor-tiers",
    response_model=SponsorTierResponse,
    status_code=status.HTTP_201_CREATED
)
def create_sponsor_tier(
    org_id: str,
    event_id: str,
    tier_in: SponsorTierCreate,
    db: Session = Depends(get_db),
    current_user: TokenPayload = Depends(deps.get_current_user),
):
    """Create a new sponsor tier for an event."""
    if current_user.org_id != org_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")

    return sponsor_tier.create_tier(
        db, tier_in=tier_in, event_id=event_id, organization_id=org_id
    )


@router.post(
    "/organizations/{org_id}/events/{event_id}/sponsor-tiers/defaults",
    response_model=List[SponsorTierResponse],
    status_code=status.HTTP_201_CREATED
)
def create_default_tiers(
    org_id: str,
    event_id: str,
    db: Session = Depends(get_db),
    current_user: TokenPayload = Depends(deps.get_current_user),
):
    """Create default sponsor tiers (Platinum, Gold, Silver, Bronze) for an event."""
    if current_user.org_id != org_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")

    # Check if tiers already exist
    existing = sponsor_tier.get_by_event(db, event_id=event_id, active_only=False)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Sponsor tiers already exist for this event"
        )

    return sponsor_tier.create_default_tiers(db, event_id=event_id, organization_id=org_id)


@router.get(
    "/organizations/{org_id}/events/{event_id}/sponsor-tiers",
    response_model=List[SponsorTierResponse]
)
def list_sponsor_tiers(
    org_id: str,
    event_id: str,
    db: Session = Depends(get_db),
    current_user: TokenPayload = Depends(deps.get_current_user),
):
    """List all sponsor tiers for an event."""
    if current_user.org_id != org_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")

    return sponsor_tier.get_by_event(db, event_id=event_id)


@router.patch(
    "/organizations/{org_id}/sponsor-tiers/{tier_id}",
    response_model=SponsorTierResponse
)
def update_sponsor_tier(
    org_id: str,
    tier_id: str,
    tier_update: SponsorTierUpdate,
    db: Session = Depends(get_db),
    current_user: TokenPayload = Depends(deps.get_current_user),
):
    """Update a sponsor tier."""
    if current_user.org_id != org_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")

    tier = sponsor_tier.get(db, id=tier_id)
    if not tier or tier.organization_id != org_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tier not found")

    return sponsor_tier.update(db, db_obj=tier, obj_in=tier_update)


# ==================== Sponsor Endpoints ====================

@router.post(
    "/organizations/{org_id}/events/{event_id}/sponsors",
    response_model=SponsorResponse,
    status_code=status.HTTP_201_CREATED
)
def create_sponsor(
    org_id: str,
    event_id: str,
    sponsor_in: SponsorCreate,
    db: Session = Depends(get_db),
    current_user: TokenPayload = Depends(deps.get_current_user),
):
    """Add a new sponsor to an event."""
    if current_user.org_id != org_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")

    # Validate tier if provided
    if sponsor_in.tier_id:
        tier = sponsor_tier.get(db, id=sponsor_in.tier_id)
        if not tier or tier.event_id != event_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid tier for this event"
            )

    return sponsor.create_sponsor(
        db, sponsor_in=sponsor_in, event_id=event_id, organization_id=org_id
    )


@router.get(
    "/organizations/{org_id}/events/{event_id}/sponsors",
    response_model=List[SponsorWithTierResponse]
)
def list_sponsors(
    org_id: str,
    event_id: str,
    include_archived: bool = False,
    db: Session = Depends(get_db),
    current_user: TokenPayload = Depends(deps.get_current_user),
):
    """List all sponsors for an event."""
    if current_user.org_id != org_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")

    return sponsor.get_by_event(
        db, event_id=event_id, include_archived=include_archived, include_tier=True
    )


@router.get(
    "/organizations/{org_id}/sponsors/{sponsor_id}",
    response_model=SponsorWithTierResponse
)
def get_sponsor(
    org_id: str,
    sponsor_id: str,
    db: Session = Depends(get_db),
    current_user: TokenPayload = Depends(deps.get_current_user),
):
    """Get a specific sponsor."""
    if current_user.org_id != org_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")

    sponsor_obj = sponsor.get_with_tier(db, sponsor_id=sponsor_id)
    if not sponsor_obj or sponsor_obj.organization_id != org_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sponsor not found")

    return sponsor_obj


@router.patch(
    "/organizations/{org_id}/sponsors/{sponsor_id}",
    response_model=SponsorResponse
)
def update_sponsor(
    org_id: str,
    sponsor_id: str,
    sponsor_update: SponsorUpdate,
    db: Session = Depends(get_db),
    current_user: TokenPayload = Depends(deps.get_current_user),
):
    """Update a sponsor."""
    if current_user.org_id != org_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")

    sponsor_obj = sponsor.get(db, id=sponsor_id)
    if not sponsor_obj or sponsor_obj.organization_id != org_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sponsor not found")

    return sponsor.update(db, db_obj=sponsor_obj, obj_in=sponsor_update)


@router.delete(
    "/organizations/{org_id}/sponsors/{sponsor_id}",
    status_code=status.HTTP_204_NO_CONTENT
)
def archive_sponsor(
    org_id: str,
    sponsor_id: str,
    db: Session = Depends(get_db),
    current_user: TokenPayload = Depends(deps.get_current_user),
):
    """Archive (soft delete) a sponsor."""
    if current_user.org_id != org_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")

    sponsor_obj = sponsor.get(db, id=sponsor_id)
    if not sponsor_obj or sponsor_obj.organization_id != org_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sponsor not found")

    sponsor.archive(db, id=sponsor_id)


# ==================== Sponsor Invitation Endpoints ====================

@router.post(
    "/organizations/{org_id}/sponsors/{sponsor_id}/invitations",
    response_model=SponsorInvitationResponse,
    status_code=status.HTTP_201_CREATED
)
@limiter.limit("10/minute")  # Rate limit: 10 invitations per minute per IP
def invite_sponsor_representative(
    request: Request,  # Required for rate limiter
    org_id: str,
    sponsor_id: str,
    invitation_in: SponsorInvitationCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: TokenPayload = Depends(deps.get_current_user),
):
    """Invite a user to be a sponsor representative."""
    if current_user.org_id != org_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")

    sponsor_obj = sponsor.get(db, id=sponsor_id)
    if not sponsor_obj or sponsor_obj.organization_id != org_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sponsor not found")

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
                detail=f"Maximum representatives ({sponsor_obj.tier.max_representatives}) reached"
            )

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
        inviter_name=current_user.full_name,
        role=invitation.role,
        personal_message=invitation.personal_message
    )

    logger.info(f"Sponsor invitation created: {invitation.id} for {invitation.email}")
    return invitation


@router.get(
    "/organizations/{org_id}/sponsors/{sponsor_id}/invitations",
    response_model=List[SponsorInvitationResponse]
)
def list_invitations(
    org_id: str,
    sponsor_id: str,
    status_filter: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: TokenPayload = Depends(deps.get_current_user),
):
    """List all invitations for a sponsor."""
    if current_user.org_id != org_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")

    return sponsor_invitation.get_by_sponsor(db, sponsor_id=sponsor_id, status=status_filter)


@router.delete(
    "/organizations/{org_id}/invitations/{invitation_id}",
    status_code=status.HTTP_204_NO_CONTENT
)
def revoke_invitation(
    org_id: str,
    invitation_id: str,
    db: Session = Depends(get_db),
    current_user: TokenPayload = Depends(deps.get_current_user),
):
    """Revoke a pending invitation."""
    if current_user.org_id != org_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")

    invitation = sponsor_invitation.get(db, id=invitation_id)
    if not invitation:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invitation not found")

    # Verify organization owns this invitation's sponsor
    sponsor_obj = sponsor.get(db, id=invitation.sponsor_id)
    if not sponsor_obj or sponsor_obj.organization_id != org_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")

    sponsor_invitation.revoke_invitation(db, invitation_id=invitation_id)


# ==================== Invitation Acceptance (Public) ====================

def _get_user_org_service_url() -> str:
    """Get the user-and-org-service internal URL (base URL without /graphql)."""
    url = getattr(settings, 'USER_SERVICE_URL', 'http://localhost:3000')
    # Strip /graphql suffix if present (common misconfiguration)
    if url.endswith('/graphql'):
        url = url[:-8]  # Remove '/graphql'
    return url.rstrip('/')


def _validate_invitation(db: Session, token: str):
    """
    Validate an invitation token and return the invitation if valid.
    Raises HTTPException if invalid.
    """
    from datetime import datetime, timezone

    invitation = sponsor_invitation.get_by_token(db, token=token)
    if not invitation:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invalid invitation token")

    if invitation.status != 'pending':
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invitation is {invitation.status}"
        )

    if invitation.expires_at < datetime.now(timezone.utc):
        invitation.status = 'expired'
        db.commit()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invitation has expired")

    return invitation


@router.get(
    "/sponsor-invitations/{token}/preview",
    response_model=SponsorInvitationPreviewResponse
)
def preview_sponsor_invitation(
    token: str,
    db: Session = Depends(get_db),
):
    """
    Preview a sponsor invitation before acceptance.
    Returns invitation details and whether the user already has an account.
    No authentication required - this is a public endpoint.
    """
    invitation = _validate_invitation(db, token)

    # Get sponsor details
    sponsor_obj = sponsor.get(db, id=invitation.sponsor_id)
    if not sponsor_obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sponsor not found")

    # Check if user exists by calling user-and-org-service
    user_exists = False
    existing_user_first_name = None
    check_failed = False

    try:
        user_org_url = _get_user_org_service_url()
        logger.info(f"Checking if user exists: {user_org_url}, email={invitation.email}")
        with httpx.Client(timeout=10.0) as client:
            response = client.get(
                f"{user_org_url}/internal/sponsor-invitations/check-email",
                params={"email": invitation.email},
                headers={"x-internal-api-key": settings.INTERNAL_API_KEY}
            )
            logger.info(f"Check email response: status={response.status_code}")
            if response.status_code == 200:
                data = response.json()
                user_exists = data.get("userExists", False)
                existing_user_first_name = data.get("existingUserFirstName")
                logger.info(f"User exists check: exists={user_exists}")
            else:
                logger.warning(f"Check email failed: {response.status_code} - {response.text}")
                check_failed = True
    except Exception as e:
        logger.warning(f"Failed to check if user exists: {e}")
        check_failed = True
        # Continue without user existence check - frontend will handle

    # If check failed and we can't determine user existence, be safe and assume they might exist
    # This prevents the confusing "account already exists" error during acceptance
    if check_failed:
        logger.warning(f"Could not determine if user exists - defaulting to exists=True for safety")
        user_exists = True  # Safer to ask for password than to try creating duplicate account

    # Role display names
    role_names = {
        "admin": "Admin",
        "representative": "Representative",
        "booth_staff": "Booth Staff",
        "viewer": "Viewer"
    }

    return SponsorInvitationPreviewResponse(
        email=invitation.email,
        sponsor_name=sponsor_obj.company_name,
        sponsor_logo_url=sponsor_obj.company_logo_url,
        inviter_name="Event Organizer",  # We don't have inviter details stored
        role_name=role_names.get(invitation.role, invitation.role.title()),
        user_exists=user_exists,
        existing_user_first_name=existing_user_first_name,
        expires_at=invitation.expires_at,
    )


@router.post(
    "/sponsor-invitations/{token}/accept/new-user",
    response_model=AcceptInvitationResponse
)
def accept_invitation_new_user(
    token: str,
    request: AcceptInvitationNewUserRequest,
    db: Session = Depends(get_db),
):
    """
    Accept a sponsor invitation as a NEW user (no existing account).
    Creates a new user account and adds them as a sponsor representative.
    No authentication required - user is created as part of this flow.
    """
    if token != request.token:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Token mismatch")

    invitation = _validate_invitation(db, token)

    # Get sponsor details
    sponsor_obj = sponsor.get(db, id=invitation.sponsor_id)
    if not sponsor_obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sponsor not found")

    # Create user in user-and-org-service
    user_org_url = _get_user_org_service_url()
    logger.info(f"Creating user in user-and-org-service: {user_org_url}")
    try:
        with httpx.Client(timeout=15.0) as client:
            create_url = f"{user_org_url}/internal/sponsor-invitations/create-user"
            payload = {
                "email": invitation.email,
                "first_name": request.first_name,
                "last_name": request.last_name,
                "password": request.password,
                "sponsorId": sponsor_obj.id,
            }
            logger.info(f"POST {create_url} with email={invitation.email}")

            response = client.post(
                create_url,
                json=payload,
                headers={"x-internal-api-key": settings.INTERNAL_API_KEY}
            )

            logger.info(f"User service response: status={response.status_code}")

            if response.status_code != 200 and response.status_code != 201:
                try:
                    error_data = response.json()
                    logger.error(f"User service error response: {error_data}")
                    # NestJS returns errors with 'message' field
                    error_detail = error_data.get("message", "Failed to create user account")
                except Exception:
                    error_detail = response.text or "Failed to create user account"
                    logger.error(f"User service error (non-JSON): {error_detail}")
                raise HTTPException(status_code=response.status_code, detail=error_detail)

            user_data = response.json()
            logger.info(f"User created successfully: user_id={user_data.get('user', {}).get('id')}")
    except httpx.HTTPError as e:
        logger.error(f"HTTP error connecting to user-and-org-service: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Unable to create user account. Please try again."
        )

    # Create sponsor user relationship
    sponsor_user_in = SponsorUserCreate(
        user_id=user_data["user"]["id"],
        role=invitation.role,
        can_view_leads=invitation.can_view_leads,
        can_export_leads=invitation.can_export_leads,
        can_message_attendees=invitation.can_message_attendees,
        can_manage_booth=invitation.can_manage_booth,
        can_invite_others=invitation.can_invite_others,
    )

    sponsor_user.create_sponsor_user(
        db, user_in=sponsor_user_in, sponsor_id=invitation.sponsor_id
    )

    # Mark invitation as accepted
    sponsor_invitation.accept_invitation(db, invitation=invitation, user_id=user_data["user"]["id"])

    logger.info(f"New user {user_data['user']['id']} accepted sponsor invitation {invitation.id}")

    return AcceptInvitationResponse(
        message=f"Welcome! Your account has been created and you are now a {invitation.role} for {sponsor_obj.company_name}.",
        sponsor_id=sponsor_obj.id,
        sponsor_name=sponsor_obj.company_name,
        event_id=sponsor_obj.event_id,
        role=invitation.role,
        user=user_data["user"],
        access_token=user_data["access_token"],
    )


@router.post(
    "/sponsor-invitations/{token}/accept/existing-user",
    response_model=AcceptInvitationResponse
)
def accept_invitation_existing_user(
    token: str,
    request: AcceptInvitationExistingUserRequest,
    db: Session = Depends(get_db),
):
    """
    Accept a sponsor invitation as an EXISTING user.
    Requires password authentication to verify account ownership.
    No JWT authentication required - password verification happens here.
    """
    if token != request.token:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Token mismatch")

    invitation = _validate_invitation(db, token)

    # Get sponsor details
    sponsor_obj = sponsor.get(db, id=invitation.sponsor_id)
    if not sponsor_obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sponsor not found")

    # Verify user in user-and-org-service
    user_org_url = _get_user_org_service_url()
    logger.info(f"Verifying user in user-and-org-service: {user_org_url}")
    try:
        with httpx.Client(timeout=15.0) as client:
            verify_url = f"{user_org_url}/internal/sponsor-invitations/verify-user"
            logger.info(f"POST {verify_url} with email={invitation.email}")

            response = client.post(
                verify_url,
                json={
                    "email": invitation.email,
                    "password": request.password,
                    "sponsorId": sponsor_obj.id,
                },
                headers={"x-internal-api-key": settings.INTERNAL_API_KEY}
            )

            logger.info(f"Verify user response: status={response.status_code}")

            if response.status_code == 401:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid password. Please enter your existing account password."
                )
            elif response.status_code != 200:
                try:
                    error_data = response.json()
                    logger.error(f"Verify user error response: {error_data}")
                    error_detail = error_data.get("message", "Failed to verify user")
                except Exception:
                    error_detail = response.text or "Failed to verify user"
                    logger.error(f"Verify user error (non-JSON): {error_detail}")
                raise HTTPException(status_code=response.status_code, detail=error_detail)

            user_data = response.json()
            logger.info(f"User verified successfully: user_id={user_data.get('user', {}).get('id')}")
    except httpx.HTTPError as e:
        logger.error(f"HTTP error connecting to user-and-org-service: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Unable to verify account. Please try again."
        )

    # Check if user is already a representative
    existing = sponsor_user.get_by_user_and_sponsor(
        db, user_id=user_data["user"]["id"], sponsor_id=invitation.sponsor_id
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You are already a representative for this sponsor"
        )

    # Create sponsor user relationship
    sponsor_user_in = SponsorUserCreate(
        user_id=user_data["user"]["id"],
        role=invitation.role,
        can_view_leads=invitation.can_view_leads,
        can_export_leads=invitation.can_export_leads,
        can_message_attendees=invitation.can_message_attendees,
        can_manage_booth=invitation.can_manage_booth,
        can_invite_others=invitation.can_invite_others,
    )

    sponsor_user.create_sponsor_user(
        db, user_in=sponsor_user_in, sponsor_id=invitation.sponsor_id
    )

    # Mark invitation as accepted
    sponsor_invitation.accept_invitation(db, invitation=invitation, user_id=user_data["user"]["id"])

    logger.info(f"Existing user {user_data['user']['id']} accepted sponsor invitation {invitation.id}")

    return AcceptInvitationResponse(
        message=f"Welcome back! You are now a {invitation.role} for {sponsor_obj.company_name}.",
        sponsor_id=sponsor_obj.id,
        sponsor_name=sponsor_obj.company_name,
        event_id=sponsor_obj.event_id,
        role=invitation.role,
        user=user_data["user"],
        access_token=user_data["access_token"],
    )


@router.post("/sponsor-invitations/accept", response_model=SponsorUserResponse)
def accept_invitation(
    request: AcceptInvitationRequest,
    db: Session = Depends(get_db),
    current_user: TokenPayload = Depends(deps.get_current_user),
):
    """
    Accept a sponsor invitation (legacy endpoint - requires authentication).
    The logged-in user becomes a representative for the sponsor.

    @deprecated Use /sponsor-invitations/{token}/accept/new-user or
    /sponsor-invitations/{token}/accept/existing-user instead.
    """
    invitation = sponsor_invitation.get_by_token(db, token=request.token)
    if not invitation:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invalid invitation token")

    if invitation.status != 'pending':
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invitation is {invitation.status}"
        )

    from datetime import datetime, timezone
    if invitation.expires_at < datetime.now(timezone.utc):
        sponsor_invitation.accept_invitation  # Mark as expired
        invitation.status = 'expired'
        db.commit()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invitation has expired")

    # Check if user is already a representative
    existing = sponsor_user.get_by_user_and_sponsor(
        db, user_id=current_user.sub, sponsor_id=invitation.sponsor_id
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You are already a representative for this sponsor"
        )

    # Create sponsor user relationship
    sponsor_user_in = SponsorUserCreate(
        user_id=current_user.sub,
        role=invitation.role,
        can_view_leads=invitation.can_view_leads,
        can_export_leads=invitation.can_export_leads,
        can_message_attendees=invitation.can_message_attendees,
        can_manage_booth=invitation.can_manage_booth,
        can_invite_others=invitation.can_invite_others,
    )

    new_sponsor_user = sponsor_user.create_sponsor_user(
        db, user_in=sponsor_user_in, sponsor_id=invitation.sponsor_id
    )

    # Mark invitation as accepted
    sponsor_invitation.accept_invitation(db, invitation=invitation, user_id=current_user.sub)

    logger.info(f"User {current_user.sub} accepted sponsor invitation {invitation.id}")
    return new_sponsor_user


# ==================== Sponsor User Endpoints ====================

@router.get(
    "/organizations/{org_id}/sponsors/{sponsor_id}/users",
    response_model=List[SponsorUserResponse]
)
def list_sponsor_users(
    org_id: str,
    sponsor_id: str,
    db: Session = Depends(get_db),
    current_user: TokenPayload = Depends(deps.get_current_user),
):
    """List all representatives for a sponsor."""
    if current_user.org_id != org_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")

    return sponsor_user.get_by_sponsor(db, sponsor_id=sponsor_id)


@router.patch(
    "/organizations/{org_id}/sponsor-users/{sponsor_user_id}",
    response_model=SponsorUserResponse
)
def update_sponsor_user(
    org_id: str,
    sponsor_user_id: str,
    user_update: SponsorUserUpdate,
    db: Session = Depends(get_db),
    current_user: TokenPayload = Depends(deps.get_current_user),
):
    """Update a sponsor representative's permissions."""
    if current_user.org_id != org_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")

    su = sponsor_user.get(db, id=sponsor_user_id)
    if not su:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sponsor user not found")

    # Verify organization owns this sponsor
    sponsor_obj = sponsor.get(db, id=su.sponsor_id)
    if not sponsor_obj or sponsor_obj.organization_id != org_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")

    return sponsor_user.update(db, db_obj=su, obj_in=user_update)


@router.delete(
    "/organizations/{org_id}/sponsor-users/{sponsor_user_id}",
    status_code=status.HTTP_204_NO_CONTENT
)
def remove_sponsor_user(
    org_id: str,
    sponsor_user_id: str,
    db: Session = Depends(get_db),
    current_user: TokenPayload = Depends(deps.get_current_user),
):
    """Remove a representative from a sponsor."""
    if current_user.org_id != org_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")

    su = sponsor_user.get(db, id=sponsor_user_id)
    if not su:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sponsor user not found")

    sponsor_obj = sponsor.get(db, id=su.sponsor_id)
    if not sponsor_obj or sponsor_obj.organization_id != org_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")

    su.is_active = False
    db.commit()


# ==================== Sponsor Lead Endpoints (For Sponsors) ====================

@router.get("/my-sponsors", response_model=List[SponsorResponse])
def get_my_sponsors(
    event_id: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: TokenPayload = Depends(deps.get_current_user),
):
    """Get all sponsors the current user represents."""
    return sponsor.get_by_user(db, user_id=current_user.sub, event_id=event_id)


# ==================== Internal API Endpoints ====================

@router.get(
    "/internal/user/{user_id}/sponsor-status",
    response_model=UserSponsorStatusResponse
)
def get_user_sponsor_status(
    user_id: str,
    db: Session = Depends(get_db),
    internal_api_key: str = Depends(deps.get_internal_api_key),
):
    """
    Check if a user is a sponsor representative.
    Internal endpoint for user-and-org-service to call during login.
    """
    # Get all sponsors for this user
    user_sponsors = sponsor.get_by_user(db, user_id=user_id)

    # Build sponsor summaries with role info
    sponsor_summaries = []
    for s in user_sponsors:
        # Get the user's role for this sponsor
        su = sponsor_user.get_by_user_and_sponsor(db, user_id=user_id, sponsor_id=s.id)
        role = su.role if su else None

        sponsor_summaries.append(SponsorSummary(
            id=s.id,
            event_id=s.event_id,
            company_name=s.company_name,
            role=role
        ))

    return UserSponsorStatusResponse(
        is_sponsor=len(user_sponsors) > 0,
        sponsor_count=len(user_sponsors),
        sponsors=sponsor_summaries
    )


@router.get("/sponsors/{sponsor_id}/leads", response_model=List[SponsorLeadResponse])
def get_sponsor_leads(
    sponsor_id: str,
    intent_level: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: TokenPayload = Depends(deps.get_current_user),
):
    """Get leads for a sponsor (for sponsor representatives)."""
    # Verify user is a sponsor representative with view permission
    su = sponsor_user.get_by_user_and_sponsor(
        db, user_id=current_user.sub, sponsor_id=sponsor_id
    )
    if not su or not su.is_active or not su.can_view_leads:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to view leads")

    # Update last active
    sponsor_user.update_last_active(db, sponsor_user_id=su.id)

    return sponsor_lead.get_by_sponsor(
        db, sponsor_id=sponsor_id, intent_level=intent_level, skip=skip, limit=limit
    )


@router.get("/sponsors/{sponsor_id}/leads/stats", response_model=SponsorStats)
def get_sponsor_lead_stats(
    sponsor_id: str,
    db: Session = Depends(get_db),
    current_user: TokenPayload = Depends(deps.get_current_user),
):
    """Get lead statistics for a sponsor."""
    su = sponsor_user.get_by_user_and_sponsor(
        db, user_id=current_user.sub, sponsor_id=sponsor_id
    )
    if not su or not su.is_active or not su.can_view_leads:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")

    return sponsor_lead.get_stats(db, sponsor_id=sponsor_id)


@router.patch("/sponsors/{sponsor_id}/booth-settings", response_model=SponsorResponse)
def update_sponsor_booth_settings(
    sponsor_id: str,
    settings_update: SponsorBoothSettingsUpdate,
    db: Session = Depends(get_db),
    current_user: TokenPayload = Depends(deps.get_current_user),
):
    """
    Update booth settings for a sponsor.

    This endpoint allows sponsor representatives to update their own
    booth settings (description, social links, notification email, etc.)
    without requiring organizer permissions.
    """
    # Verify user is a representative for this sponsor
    su = sponsor_user.get_by_user_and_sponsor(
        db, user_id=current_user.sub, sponsor_id=sponsor_id
    )
    if not su or not su.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")

    # Get the sponsor
    sponsor_obj = sponsor.get(db, id=sponsor_id)
    if not sponsor_obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sponsor not found")

    # Update only the allowed fields
    update_data = settings_update.model_dump(exclude_unset=True)

    return sponsor.update(db, db_obj=sponsor_obj, obj_in=update_data)


@router.patch("/sponsors/{sponsor_id}/leads/{lead_id}", response_model=SponsorLeadResponse)
def update_lead_follow_up(
    sponsor_id: str,
    lead_id: str,
    lead_update: SponsorLeadUpdate,
    db: Session = Depends(get_db),
    current_user: TokenPayload = Depends(deps.get_current_user),
):
    """Update a lead's follow-up status."""
    su = sponsor_user.get_by_user_and_sponsor(
        db, user_id=current_user.sub, sponsor_id=sponsor_id
    )
    if not su or not su.is_active or not su.can_view_leads:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")

    lead = sponsor_lead.get(db, id=lead_id)
    if not lead or lead.sponsor_id != sponsor_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lead not found")

    if lead_update.follow_up_status:
        return sponsor_lead.update_follow_up(
            db,
            lead_id=lead_id,
            status=lead_update.follow_up_status,
            notes=lead_update.follow_up_notes,
            user_id=current_user.sub
        )

    return sponsor_lead.update(db, db_obj=lead, obj_in=lead_update)


# ==================== Lead Capture Endpoint (For Events Service) ====================

@router.post(
    "/events/{event_id}/sponsors/{sponsor_id}/capture-lead",
    response_model=SponsorLeadResponse,
    status_code=status.HTTP_201_CREATED
)
@limiter.limit("30/minute")  # Rate limit: 30 lead captures per minute per IP
def capture_lead(
    request: Request,  # Required for rate limiter
    event_id: str,
    sponsor_id: str,
    lead_in: SponsorLeadCreate,
    db: Session = Depends(get_db),
    current_user: Optional[TokenPayload] = Depends(deps.get_current_user_optional),
    internal_api_key: Optional[str] = Depends(deps.get_internal_api_key_optional),
):
    """
    Capture a lead for a sponsor.
    Called when an attendee interacts with a sponsor (booth visit, content download, etc.)

    Security: Requires either user authentication OR internal API key.
    - If user authenticated: user_id in request must match the authenticated user
    - If internal API key: trusted service-to-service call
    """
    # Security check: require either user auth or internal API key
    if not current_user and not internal_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required"
        )

    # If user is authenticated, verify they can only capture leads for themselves
    if current_user and not internal_api_key:
        if lead_in.user_id != current_user.sub:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot capture leads for other users"
            )

    sponsor_obj = sponsor.get(db, id=sponsor_id)
    if not sponsor_obj or sponsor_obj.event_id != event_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sponsor not found")

    if not sponsor_obj.lead_capture_enabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Lead capture is disabled for this sponsor"
        )

    lead = sponsor_lead.capture_lead(
        db, lead_in=lead_in, sponsor_id=sponsor_id, event_id=event_id
    )

    # Emit real-time event for sponsor dashboard
    emit_lead_captured_event(
        sponsor_id=sponsor_id,
        lead_data={
            "id": lead.id,
            "user_id": lead.user_id,
            "user_name": lead.user_name,
            "user_email": lead.user_email,
            "user_company": lead.user_company,
            "user_title": lead.user_title,
            "intent_score": lead.intent_score,
            "intent_level": lead.intent_level,
            "interaction_type": lead_in.interaction_type,
            "created_at": lead.created_at.isoformat() if lead.created_at else None,
        }
    )

    # Send email notification if configured
    if sponsor_obj.lead_notification_email and lead.intent_level in ['hot', 'warm']:
        from app.crud import event as crud_event
        event_obj = crud_event.get(db, id=event_id)
        event_name = event_obj.name if event_obj else "Event"

        send_lead_notification_email(
            notification_email=sponsor_obj.lead_notification_email,
            sponsor_name=sponsor_obj.company_name,
            lead_name=lead.user_name or "Unknown",
            lead_company=lead.user_company,
            lead_title=lead.user_title,
            intent_level=lead.intent_level,
            interaction_type=lead_in.interaction_type,
            event_name=event_name
        )

    return lead


# ==================== Manual Lead Capture (For Sponsor Representatives) ====================

@router.post(
    "/sponsors/{sponsor_id}/capture-lead-manual",
    response_model=SponsorLeadResponse,
    status_code=status.HTTP_201_CREATED
)
def capture_lead_manual(
    sponsor_id: str,
    lead_in: ManualLeadCaptureCreate,
    db: Session = Depends(get_db),
    current_user: TokenPayload = Depends(deps.get_current_user),
):
    """
    Manually capture a lead for a sponsor.
    This endpoint allows sponsor representatives to manually enter lead information
    (e.g., after talking to someone at their booth who didn't have a badge scanned).

    A unique user_id is generated based on the email to prevent duplicates.
    """
    import hashlib

    # Verify user is a sponsor representative
    su = sponsor_user.get_by_user_and_sponsor(
        db, user_id=current_user.sub, sponsor_id=sponsor_id
    )
    if not su or not su.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")

    sponsor_obj = sponsor.get(db, id=sponsor_id)
    if not sponsor_obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sponsor not found")

    if not sponsor_obj.lead_capture_enabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Lead capture is disabled for this sponsor"
        )

    # Generate a deterministic user_id from email to prevent duplicate leads
    # Format: manual_<hash of email>
    email_hash = hashlib.sha256(lead_in.user_email.lower().encode()).hexdigest()[:16]
    generated_user_id = f"manual_{email_hash}"

    # Create lead using the existing CRUD method
    lead_create = SponsorLeadCreate(
        user_id=generated_user_id,
        user_name=lead_in.user_name,
        user_email=lead_in.user_email,
        user_company=lead_in.user_company,
        user_title=lead_in.user_title,
        interaction_type=lead_in.interaction_type,
        interaction_metadata={"notes": lead_in.notes, "captured_by": current_user.sub} if lead_in.notes else {"captured_by": current_user.sub},
    )

    lead = sponsor_lead.capture_lead(
        db, lead_in=lead_create, sponsor_id=sponsor_id, event_id=sponsor_obj.event_id
    )

    # Emit real-time event
    emit_lead_captured_event(
        sponsor_id=sponsor_id,
        lead_data={
            "id": lead.id,
            "user_id": lead.user_id,
            "user_name": lead.user_name,
            "user_email": lead.user_email,
            "user_company": lead.user_company,
            "user_title": lead.user_title,
            "intent_score": lead.intent_score,
            "intent_level": lead.intent_level,
            "interaction_type": lead_in.interaction_type,
            "created_at": lead.created_at.isoformat() if lead.created_at else None,
        }
    )

    logger.info(f"Manual lead captured by {current_user.sub} for sponsor {sponsor_id}: {lead.user_email}")
    return lead
