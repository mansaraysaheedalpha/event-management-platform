# app/graphql/sponsor_mutations.py
"""
GraphQL mutations for sponsor management.
"""

import strawberry
from typing import Optional, List
from strawberry.types import Info
from fastapi import HTTPException
import json

from .sponsor_types import (
    SponsorTierType,
    SponsorTierCreateInput,
    SponsorTierUpdateInput,
    SponsorType,
    SponsorCreateInput,
    SponsorUpdateInput,
    SponsorInvitationType,
    SponsorInvitationCreateInput,
    SponsorInvitationAcceptResponse,
    SponsorUserType,
    SponsorLeadType,
    SponsorLeadUpdateInput,
)
from ..schemas.sponsor import (
    SponsorTierCreate,
    SponsorTierUpdate,
    SponsorCreate,
    SponsorUpdate,
    SponsorInvitationCreate,
    SponsorUserCreate,
    SponsorLeadUpdate,
)
from .. import crud


class SponsorMutations:
    """Sponsor-related mutations."""

    # ============================================
    # Sponsor Tier Mutations
    # ============================================

    def create_sponsor_tier(
        self, event_id: str, input: SponsorTierCreateInput, info: Info
    ) -> SponsorTierType:
        """Create a new sponsor tier for an event."""
        user = info.context.user
        if not user or not user.get("orgId"):
            raise HTTPException(status_code=403, detail="Not authorized")

        db = info.context.db
        org_id = user["orgId"]

        # Verify event exists and belongs to org
        event = crud.event.get(db, id=event_id)
        if not event or event.organization_id != org_id:
            raise HTTPException(status_code=404, detail="Event not found")

        tier_schema = SponsorTierCreate(
            name=input.name,
            display_order=input.display_order,
            color=input.color,
            benefits=input.benefits or [],
            booth_size=input.booth_size,
            logo_placement=input.logo_placement,
            max_representatives=input.max_representatives,
            can_capture_leads=input.can_capture_leads,
            can_export_leads=input.can_export_leads,
            can_send_messages=input.can_send_messages,
            price_cents=input.price_cents,
            currency=input.currency,
        )

        return crud.sponsor_tier.create_tier(
            db,
            tier_in=tier_schema,
            event_id=event_id,
            organization_id=org_id
        )

    def update_sponsor_tier(
        self, tier_id: str, input: SponsorTierUpdateInput, info: Info
    ) -> SponsorTierType:
        """Update a sponsor tier."""
        user = info.context.user
        if not user or not user.get("orgId"):
            raise HTTPException(status_code=403, detail="Not authorized")

        db = info.context.db
        org_id = user["orgId"]

        tier = crud.sponsor_tier.get(db, id=tier_id)
        if not tier or tier.organization_id != org_id:
            raise HTTPException(status_code=404, detail="Tier not found")

        update_data = {k: v for k, v in input.__dict__.items() if v is not None}
        tier_update = SponsorTierUpdate(**update_data)

        return crud.sponsor_tier.update(db, db_obj=tier, obj_in=tier_update)

    def delete_sponsor_tier(self, tier_id: str, info: Info) -> bool:
        """Delete a sponsor tier (sets is_active to False)."""
        user = info.context.user
        if not user or not user.get("orgId"):
            raise HTTPException(status_code=403, detail="Not authorized")

        db = info.context.db
        org_id = user["orgId"]

        tier = crud.sponsor_tier.get(db, id=tier_id)
        if not tier or tier.organization_id != org_id:
            raise HTTPException(status_code=404, detail="Tier not found")

        # Soft delete by setting is_active to False
        crud.sponsor_tier.update(db, db_obj=tier, obj_in={"is_active": False})
        return True

    # ============================================
    # Sponsor Mutations
    # ============================================

    def create_sponsor(
        self, event_id: str, input: SponsorCreateInput, info: Info
    ) -> SponsorType:
        """Create a new sponsor for an event."""
        user = info.context.user
        if not user or not user.get("orgId"):
            raise HTTPException(status_code=403, detail="Not authorized")

        db = info.context.db
        org_id = user["orgId"]

        # Verify event exists and belongs to org
        event = crud.event.get(db, id=event_id)
        if not event or event.organization_id != org_id:
            raise HTTPException(status_code=404, detail="Event not found")

        # Parse JSON fields if provided
        social_links = None
        if input.social_links:
            try:
                social_links = json.loads(input.social_links)
            except json.JSONDecodeError:
                raise HTTPException(status_code=400, detail="Invalid JSON for social_links")

        marketing_assets = None
        if input.marketing_assets:
            try:
                marketing_assets = json.loads(input.marketing_assets)
            except json.JSONDecodeError:
                raise HTTPException(status_code=400, detail="Invalid JSON for marketing_assets")

        custom_fields = None
        if input.custom_fields:
            try:
                custom_fields = json.loads(input.custom_fields)
            except json.JSONDecodeError:
                raise HTTPException(status_code=400, detail="Invalid JSON for custom_fields")

        sponsor_schema = SponsorCreate(
            tier_id=input.tier_id,
            company_name=input.company_name,
            company_description=input.company_description,
            company_website=input.company_website,
            company_logo_url=input.company_logo_url,
            contact_name=input.contact_name,
            contact_email=input.contact_email,
            contact_phone=input.contact_phone,
            booth_number=input.booth_number,
            booth_description=input.booth_description,
            custom_booth_url=input.custom_booth_url,
            social_links=social_links or {},
            marketing_assets=marketing_assets or [],
            lead_capture_enabled=input.lead_capture_enabled,
            lead_notification_email=input.lead_notification_email,
            custom_fields=custom_fields or {},
        )

        return crud.sponsor.create_sponsor(
            db,
            sponsor_in=sponsor_schema,
            event_id=event_id,
            organization_id=org_id
        )

    def update_sponsor(
        self, sponsor_id: str, input: SponsorUpdateInput, info: Info
    ) -> SponsorType:
        """Update a sponsor."""
        user = info.context.user
        if not user or not user.get("orgId"):
            raise HTTPException(status_code=403, detail="Not authorized")

        db = info.context.db
        org_id = user["orgId"]

        sponsor = crud.sponsor.get(db, id=sponsor_id)
        if not sponsor or sponsor.organization_id != org_id:
            raise HTTPException(status_code=404, detail="Sponsor not found")

        # Parse JSON fields if provided
        update_data = {}
        for k, v in input.__dict__.items():
            if v is not None:
                if k in ['social_links', 'marketing_assets', 'custom_fields'] and isinstance(v, str):
                    try:
                        update_data[k] = json.loads(v)
                    except json.JSONDecodeError:
                        raise HTTPException(status_code=400, detail=f"Invalid JSON for {k}")
                else:
                    update_data[k] = v

        sponsor_update = SponsorUpdate(**update_data)
        return crud.sponsor.update(db, db_obj=sponsor, obj_in=sponsor_update)

    def archive_sponsor(self, sponsor_id: str, info: Info) -> SponsorType:
        """Archive a sponsor."""
        user = info.context.user
        if not user or not user.get("orgId"):
            raise HTTPException(status_code=403, detail="Not authorized")

        db = info.context.db
        org_id = user["orgId"]

        sponsor = crud.sponsor.get(db, id=sponsor_id)
        if not sponsor or sponsor.organization_id != org_id:
            raise HTTPException(status_code=404, detail="Sponsor not found")

        return crud.sponsor.update(db, db_obj=sponsor, obj_in={"is_archived": True})

    def restore_sponsor(self, sponsor_id: str, info: Info) -> SponsorType:
        """Restore an archived sponsor."""
        user = info.context.user
        if not user or not user.get("orgId"):
            raise HTTPException(status_code=403, detail="Not authorized")

        db = info.context.db
        org_id = user["orgId"]

        sponsor = crud.sponsor.get(db, id=sponsor_id)
        if not sponsor or sponsor.organization_id != org_id:
            raise HTTPException(status_code=404, detail="Sponsor not found")

        return crud.sponsor.update(db, db_obj=sponsor, obj_in={"is_archived": False})

    # ============================================
    # Sponsor Invitation Mutations
    # ============================================

    def create_sponsor_invitation(
        self, sponsor_id: str, input: SponsorInvitationCreateInput, info: Info
    ) -> SponsorInvitationType:
        """Create and send an invitation to join a sponsor team."""
        user = info.context.user
        if not user or not user.get("orgId"):
            raise HTTPException(status_code=403, detail="Not authorized")

        db = info.context.db
        org_id = user["orgId"]
        user_id = user["sub"]

        sponsor = crud.sponsor.get(db, id=sponsor_id)
        if not sponsor or sponsor.organization_id != org_id:
            raise HTTPException(status_code=404, detail="Sponsor not found")

        invitation_schema = SponsorInvitationCreate(
            email=input.email,
            role=input.role,
            can_view_leads=input.can_view_leads,
            can_export_leads=input.can_export_leads,
            can_message_attendees=input.can_message_attendees,
            can_manage_booth=input.can_manage_booth,
            can_invite_others=input.can_invite_others,
            personal_message=input.personal_message,
        )

        return crud.sponsor_invitation.create_invitation(
            db,
            invitation_in=invitation_schema,
            sponsor_id=sponsor_id,
            invited_by_user_id=user_id
        )

    def resend_sponsor_invitation(
        self, invitation_id: str, info: Info
    ) -> SponsorInvitationType:
        """Resend a pending invitation."""
        user = info.context.user
        if not user or not user.get("orgId"):
            raise HTTPException(status_code=403, detail="Not authorized")

        db = info.context.db
        org_id = user["orgId"]

        invitation = crud.sponsor_invitation.get(db, id=invitation_id)
        if not invitation:
            raise HTTPException(status_code=404, detail="Invitation not found")

        sponsor = crud.sponsor.get(db, id=invitation.sponsor_id)
        if not sponsor or sponsor.organization_id != org_id:
            raise HTTPException(status_code=404, detail="Sponsor not found")

        if invitation.status != "pending":
            raise HTTPException(status_code=400, detail="Can only resend pending invitations")

        # For now, just return the existing invitation
        # In a real system, this would trigger an email resend
        return invitation

    def revoke_sponsor_invitation(self, invitation_id: str, info: Info) -> bool:
        """Revoke a pending invitation."""
        user = info.context.user
        if not user or not user.get("orgId"):
            raise HTTPException(status_code=403, detail="Not authorized")

        db = info.context.db
        org_id = user["orgId"]

        invitation = crud.sponsor_invitation.get(db, id=invitation_id)
        if not invitation:
            raise HTTPException(status_code=404, detail="Invitation not found")

        sponsor = crud.sponsor.get(db, id=invitation.sponsor_id)
        if not sponsor or sponsor.organization_id != org_id:
            raise HTTPException(status_code=404, detail="Sponsor not found")

        crud.sponsor_invitation.revoke_invitation(db, invitation_id=invitation_id)
        return True

    def accept_sponsor_invitation(
        self, token: str, info: Info
    ) -> SponsorInvitationAcceptResponse:
        """Accept a sponsor invitation using the token."""
        user = info.context.user
        if not user or not user.get("sub"):
            raise HTTPException(status_code=401, detail="Authentication required")

        db = info.context.db
        user_id = user["sub"]

        # Find invitation by token
        invitation = crud.sponsor_invitation.get_by_token(db, token=token)
        if not invitation:
            return SponsorInvitationAcceptResponse(
                success=False,
                message="Invalid or expired invitation",
                sponsor_user=None
            )

        if invitation.status != "pending":
            return SponsorInvitationAcceptResponse(
                success=False,
                message="Invitation has already been used or revoked",
                sponsor_user=None
            )

        from datetime import datetime, timezone
        if invitation.expires_at < datetime.now(timezone.utc):
            return SponsorInvitationAcceptResponse(
                success=False,
                message="Invitation has expired",
                sponsor_user=None
            )

        # Mark invitation as accepted
        crud.sponsor_invitation.accept_invitation(db, invitation=invitation, user_id=user_id)

        # Create sponsor user
        sponsor_user_schema = SponsorUserCreate(
            user_id=user_id,
            role=invitation.role,
            can_view_leads=invitation.can_view_leads,
            can_export_leads=invitation.can_export_leads,
            can_message_attendees=invitation.can_message_attendees,
            can_manage_booth=invitation.can_manage_booth,
            can_invite_others=invitation.can_invite_others,
        )
        sponsor_user = crud.sponsor_user.create_sponsor_user(
            db, user_in=sponsor_user_schema, sponsor_id=invitation.sponsor_id
        )

        return SponsorInvitationAcceptResponse(
            success=True,
            message="Successfully joined sponsor team",
            sponsor_user=sponsor_user
        )

    # ============================================
    # Sponsor User Mutations
    # ============================================

    def update_sponsor_user(
        self, sponsor_user_id: str, role: Optional[str] = None,
        can_view_leads: Optional[bool] = None,
        can_export_leads: Optional[bool] = None,
        can_message_attendees: Optional[bool] = None,
        can_manage_booth: Optional[bool] = None,
        can_invite_others: Optional[bool] = None,
        is_active: Optional[bool] = None,
        info: Info = None
    ) -> SponsorUserType:
        """Update a sponsor user's permissions."""
        user = info.context.user
        if not user or not user.get("orgId"):
            raise HTTPException(status_code=403, detail="Not authorized")

        db = info.context.db
        org_id = user["orgId"]

        sponsor_user_obj = crud.sponsor_user.get(db, id=sponsor_user_id)
        if not sponsor_user_obj:
            raise HTTPException(status_code=404, detail="Sponsor user not found")

        sponsor = crud.sponsor.get(db, id=sponsor_user_obj.sponsor_id)
        if not sponsor or sponsor.organization_id != org_id:
            raise HTTPException(status_code=404, detail="Sponsor not found")

        update_data = {}
        if role is not None:
            update_data['role'] = role
        if can_view_leads is not None:
            update_data['can_view_leads'] = can_view_leads
        if can_export_leads is not None:
            update_data['can_export_leads'] = can_export_leads
        if can_message_attendees is not None:
            update_data['can_message_attendees'] = can_message_attendees
        if can_manage_booth is not None:
            update_data['can_manage_booth'] = can_manage_booth
        if can_invite_others is not None:
            update_data['can_invite_others'] = can_invite_others
        if is_active is not None:
            update_data['is_active'] = is_active

        return crud.sponsor_user.update(db, db_obj=sponsor_user_obj, obj_in=update_data)

    def remove_sponsor_user(self, sponsor_user_id: str, info: Info) -> bool:
        """Remove a user from a sponsor team."""
        user = info.context.user
        if not user or not user.get("orgId"):
            raise HTTPException(status_code=403, detail="Not authorized")

        db = info.context.db
        org_id = user["orgId"]

        sponsor_user_obj = crud.sponsor_user.get(db, id=sponsor_user_id)
        if not sponsor_user_obj:
            raise HTTPException(status_code=404, detail="Sponsor user not found")

        sponsor = crud.sponsor.get(db, id=sponsor_user_obj.sponsor_id)
        if not sponsor or sponsor.organization_id != org_id:
            raise HTTPException(status_code=404, detail="Sponsor not found")

        crud.sponsor_user.remove(db, id=sponsor_user_id)
        return True

    # ============================================
    # Sponsor Lead Mutations
    # ============================================

    def update_sponsor_lead(
        self, lead_id: str, input: SponsorLeadUpdateInput, info: Info
    ) -> SponsorLeadType:
        """Update a sponsor lead (follow-up status, notes, tags)."""
        user = info.context.user
        if not user or not user.get("sub"):
            raise HTTPException(status_code=401, detail="Authentication required")

        db = info.context.db
        user_id = user["sub"]

        lead = crud.sponsor_lead.get(db, id=lead_id)
        if not lead:
            raise HTTPException(status_code=404, detail="Lead not found")

        # Verify user has access to this sponsor
        sponsor_user_obj = crud.sponsor_user.get_by_user_and_sponsor(
            db, user_id=user_id, sponsor_id=lead.sponsor_id
        )
        if not sponsor_user_obj or not sponsor_user_obj.can_view_leads:
            raise HTTPException(status_code=403, detail="Not authorized to update this lead")

        update_data = {k: v for k, v in input.__dict__.items() if v is not None}
        lead_update = SponsorLeadUpdate(**update_data)

        return crud.sponsor_lead.update(db, db_obj=lead, obj_in=lead_update)

    def star_sponsor_lead(self, lead_id: str, starred: bool, info: Info) -> SponsorLeadType:
        """Star or unstar a lead."""
        user = info.context.user
        if not user or not user.get("sub"):
            raise HTTPException(status_code=401, detail="Authentication required")

        db = info.context.db
        user_id = user["sub"]

        lead = crud.sponsor_lead.get(db, id=lead_id)
        if not lead:
            raise HTTPException(status_code=404, detail="Lead not found")

        # Verify user has access to this sponsor
        sponsor_user_obj = crud.sponsor_user.get_by_user_and_sponsor(
            db, user_id=user_id, sponsor_id=lead.sponsor_id
        )
        if not sponsor_user_obj or not sponsor_user_obj.can_view_leads:
            raise HTTPException(status_code=403, detail="Not authorized")

        return crud.sponsor_lead.update(db, db_obj=lead, obj_in={"is_starred": starred})

    def archive_sponsor_lead(self, lead_id: str, info: Info) -> SponsorLeadType:
        """Archive a lead."""
        user = info.context.user
        if not user or not user.get("sub"):
            raise HTTPException(status_code=401, detail="Authentication required")

        db = info.context.db
        user_id = user["sub"]

        lead = crud.sponsor_lead.get(db, id=lead_id)
        if not lead:
            raise HTTPException(status_code=404, detail="Lead not found")

        # Verify user has access to this sponsor
        sponsor_user_obj = crud.sponsor_user.get_by_user_and_sponsor(
            db, user_id=user_id, sponsor_id=lead.sponsor_id
        )
        if not sponsor_user_obj or not sponsor_user_obj.can_view_leads:
            raise HTTPException(status_code=403, detail="Not authorized")

        return crud.sponsor_lead.update(db, db_obj=lead, obj_in={"is_archived": True})
