# app/graphql/sponsor_queries.py
"""
GraphQL queries for sponsor management.
"""

import strawberry
from typing import Optional, List
from strawberry.types import Info
from fastapi import HTTPException

from .sponsor_types import (
    SponsorTierType,
    SponsorType,
    SponsorWithTierType,
    SponsorUserType,
    SponsorInvitationType,
    SponsorLeadType,
    SponsorStatsType,
    SponsorsListResponse,
)
from .. import crud


class SponsorQueries:
    """Sponsor-related queries."""

    # ============================================
    # Sponsor Tier Queries
    # ============================================

    def event_sponsor_tiers(
        self, event_id: str, info: Info
    ) -> List[SponsorTierType]:
        """Get all sponsor tiers for an event."""
        user = info.context.user
        db = info.context.db

        # Verify event exists
        event = crud.event.get(db, id=event_id)
        if not event:
            raise HTTPException(status_code=404, detail="Event not found")

        # Allow public access to tiers if event is public
        if not event.is_public:
            if not user or not user.get("orgId"):
                raise HTTPException(status_code=403, detail="Not authorized")
            if event.organization_id != user.get("orgId"):
                raise HTTPException(status_code=403, detail="Not authorized")

        return crud.sponsor_tier.get_by_event(db, event_id=event_id)

    def sponsor_tier(
        self, tier_id: str, info: Info
    ) -> Optional[SponsorTierType]:
        """Get a single sponsor tier by ID."""
        user = info.context.user
        if not user or not user.get("orgId"):
            raise HTTPException(status_code=403, detail="Not authorized")

        db = info.context.db
        org_id = user["orgId"]

        tier = crud.sponsor_tier.get(db, id=tier_id)
        if not tier or tier.organization_id != org_id:
            return None

        return tier

    # ============================================
    # Sponsor Queries
    # ============================================

    def event_sponsors(
        self, event_id: str, info: Info,
        include_archived: bool = False,
        tier_id: Optional[str] = None
    ) -> SponsorsListResponse:
        """Get all sponsors for an event."""
        db = info.context.db
        user = info.context.user

        # Verify event exists
        event = crud.event.get(db, id=event_id)
        if not event:
            raise HTTPException(status_code=404, detail="Event not found")

        # For public events, show only active sponsors
        # For org users, show all sponsors
        is_org_user = user and user.get("orgId") == event.organization_id

        sponsors = crud.sponsor.get_by_event(
            db,
            event_id=event_id,
            include_archived=include_archived and is_org_user
        )

        # Filter by tier if specified
        if tier_id:
            sponsors = [s for s in sponsors if s.tier_id == tier_id]

        # Filter inactive if not org user
        if not is_org_user:
            sponsors = [s for s in sponsors if s.is_active and not s.is_archived]

        return SponsorsListResponse(
            sponsors=sponsors,
            total_count=len(sponsors)
        )

    def sponsor(self, sponsor_id: str, info: Info) -> Optional[SponsorType]:
        """Get a single sponsor by ID."""
        db = info.context.db
        user = info.context.user

        sponsor = crud.sponsor.get(db, id=sponsor_id)
        if not sponsor:
            return None

        # Check access
        event = crud.event.get(db, id=sponsor.event_id)
        if not event:
            return None

        is_org_user = user and user.get("orgId") == sponsor.organization_id
        is_sponsor_user = False

        if user and user.get("sub"):
            sponsor_user_obj = crud.sponsor_user.get_by_user_and_sponsor(
                db, user_id=user["sub"], sponsor_id=sponsor_id
            )
            is_sponsor_user = sponsor_user_obj is not None

        # Non-org users can only see active sponsors of public events
        if not is_org_user and not is_sponsor_user:
            if not event.is_public or not sponsor.is_active or sponsor.is_archived:
                return None

        return sponsor

    def sponsor_with_tier(
        self, sponsor_id: str, info: Info
    ) -> Optional[SponsorWithTierType]:
        """Get a sponsor with its tier information."""
        db = info.context.db
        user = info.context.user

        sponsor = crud.sponsor.get(db, id=sponsor_id)
        if not sponsor:
            return None

        is_org_user = user and user.get("orgId") == sponsor.organization_id
        is_sponsor_user = False

        if user and user.get("sub"):
            sponsor_user_obj = crud.sponsor_user.get_by_user_and_sponsor(
                db, user_id=user["sub"], sponsor_id=sponsor_id
            )
            is_sponsor_user = sponsor_user_obj is not None

        if not is_org_user and not is_sponsor_user:
            event = crud.event.get(db, id=sponsor.event_id)
            if not event or not event.is_public or not sponsor.is_active:
                return None

        tier = None
        if sponsor.tier_id:
            tier = crud.sponsor_tier.get(db, id=sponsor.tier_id)

        # Create response with tier
        return SponsorWithTierType(
            id=sponsor.id,
            organization_id=sponsor.organization_id,
            event_id=sponsor.event_id,
            tier_id=sponsor.tier_id,
            company_name=sponsor.company_name,
            company_description=sponsor.company_description,
            company_website=sponsor.company_website,
            company_logo_url=sponsor.company_logo_url,
            contact_name=sponsor.contact_name,
            contact_email=sponsor.contact_email,
            contact_phone=sponsor.contact_phone,
            booth_number=sponsor.booth_number,
            booth_description=sponsor.booth_description,
            custom_booth_url=sponsor.custom_booth_url,
            lead_capture_enabled=sponsor.lead_capture_enabled,
            lead_notification_email=sponsor.lead_notification_email,
            is_active=sponsor.is_active,
            is_featured=sponsor.is_featured,
            is_archived=sponsor.is_archived,
            created_at=sponsor.created_at,
            updated_at=sponsor.updated_at,
            tier=tier
        )

    def my_sponsors(self, info: Info) -> List[SponsorType]:
        """Get sponsors where the current user is a team member."""
        user = info.context.user
        if not user or not user.get("sub"):
            raise HTTPException(status_code=401, detail="Authentication required")

        db = info.context.db
        user_id = user["sub"]

        return crud.sponsor.get_by_user(db, user_id=user_id)

    # ============================================
    # Sponsor User Queries
    # ============================================

    def sponsor_users(
        self, sponsor_id: str, info: Info
    ) -> List[SponsorUserType]:
        """Get all users for a sponsor."""
        user = info.context.user
        if not user or not user.get("orgId"):
            raise HTTPException(status_code=403, detail="Not authorized")

        db = info.context.db
        org_id = user["orgId"]

        sponsor = crud.sponsor.get(db, id=sponsor_id)
        if not sponsor or sponsor.organization_id != org_id:
            raise HTTPException(status_code=404, detail="Sponsor not found")

        return crud.sponsor_user.get_by_sponsor(db, sponsor_id=sponsor_id)

    def my_sponsor_membership(
        self, sponsor_id: str, info: Info
    ) -> Optional[SponsorUserType]:
        """Get the current user's membership for a sponsor."""
        user = info.context.user
        if not user or not user.get("sub"):
            raise HTTPException(status_code=401, detail="Authentication required")

        db = info.context.db
        user_id = user["sub"]

        return crud.sponsor_user.get_by_user_and_sponsor(
            db, user_id=user_id, sponsor_id=sponsor_id
        )

    # ============================================
    # Sponsor Invitation Queries
    # ============================================

    def sponsor_invitations(
        self, sponsor_id: str, info: Info,
        status: Optional[str] = None
    ) -> List[SponsorInvitationType]:
        """Get all invitations for a sponsor."""
        user = info.context.user
        if not user or not user.get("orgId"):
            raise HTTPException(status_code=403, detail="Not authorized")

        db = info.context.db
        org_id = user["orgId"]

        sponsor = crud.sponsor.get(db, id=sponsor_id)
        if not sponsor or sponsor.organization_id != org_id:
            raise HTTPException(status_code=404, detail="Sponsor not found")

        return crud.sponsor_invitation.get_by_sponsor(db, sponsor_id=sponsor_id, status=status)

    def validate_sponsor_invitation(
        self, token: str, info: Info
    ) -> Optional[SponsorInvitationType]:
        """Validate an invitation token and return invitation details."""
        db = info.context.db
        invitation = crud.sponsor_invitation.get_by_token(db, token=token)

        if not invitation:
            return None

        if invitation.status != "pending":
            return None

        from datetime import datetime, timezone
        if invitation.expires_at < datetime.now(timezone.utc):
            return None

        return invitation

    # ============================================
    # Sponsor Lead Queries
    # ============================================

    def sponsor_leads(
        self, sponsor_id: str, info: Info,
        intent_level: Optional[str] = None,
        follow_up_status: Optional[str] = None,
        is_starred: Optional[bool] = None,
        include_archived: bool = False,
        limit: int = 100,
        offset: int = 0
    ) -> List[SponsorLeadType]:
        """Get leads for a sponsor."""
        user = info.context.user
        if not user or not user.get("sub"):
            raise HTTPException(status_code=401, detail="Authentication required")

        db = info.context.db
        user_id = user["sub"]

        # Verify user has access to this sponsor
        sponsor_user_obj = crud.sponsor_user.get_by_user_and_sponsor(
            db, user_id=user_id, sponsor_id=sponsor_id
        )

        # Also allow org admins
        sponsor = crud.sponsor.get(db, id=sponsor_id)
        is_org_admin = user.get("orgId") == sponsor.organization_id if sponsor else False

        if not sponsor_user_obj and not is_org_admin:
            raise HTTPException(status_code=403, detail="Not authorized to view leads")

        if sponsor_user_obj and not sponsor_user_obj.can_view_leads and not is_org_admin:
            raise HTTPException(status_code=403, detail="Not authorized to view leads")

        leads = crud.sponsor_lead.get_by_sponsor(
            db,
            sponsor_id=sponsor_id,
            intent_level=intent_level,
            include_archived=include_archived,
            skip=offset,
            limit=limit
        )

        # Apply additional filters
        if follow_up_status:
            leads = [l for l in leads if l.follow_up_status == follow_up_status]
        if is_starred is not None:
            leads = [l for l in leads if l.is_starred == is_starred]

        return leads

    def sponsor_lead(self, lead_id: str, info: Info) -> Optional[SponsorLeadType]:
        """Get a single lead by ID."""
        user = info.context.user
        if not user or not user.get("sub"):
            raise HTTPException(status_code=401, detail="Authentication required")

        db = info.context.db
        user_id = user["sub"]

        lead = crud.sponsor_lead.get(db, id=lead_id)
        if not lead:
            return None

        # Verify user has access
        sponsor_user_obj = crud.sponsor_user.get_by_user_and_sponsor(
            db, user_id=user_id, sponsor_id=lead.sponsor_id
        )

        sponsor = crud.sponsor.get(db, id=lead.sponsor_id)
        is_org_admin = user.get("orgId") == sponsor.organization_id if sponsor else False

        if not sponsor_user_obj and not is_org_admin:
            return None

        if sponsor_user_obj and not sponsor_user_obj.can_view_leads and not is_org_admin:
            return None

        return lead

    def sponsor_stats(self, sponsor_id: str, info: Info) -> SponsorStatsType:
        """Get statistics for a sponsor's leads."""
        user = info.context.user
        if not user or not user.get("sub"):
            raise HTTPException(status_code=401, detail="Authentication required")

        db = info.context.db
        user_id = user["sub"]

        # Verify user has access to this sponsor
        sponsor_user_obj = crud.sponsor_user.get_by_user_and_sponsor(
            db, user_id=user_id, sponsor_id=sponsor_id
        )

        sponsor = crud.sponsor.get(db, id=sponsor_id)
        is_org_admin = user.get("orgId") == sponsor.organization_id if sponsor else False

        if not sponsor_user_obj and not is_org_admin:
            raise HTTPException(status_code=403, detail="Not authorized")

        stats = crud.sponsor_lead.get_stats(db, sponsor_id=sponsor_id)

        return SponsorStatsType(
            total_leads=stats.get("total_leads", 0),
            hot_leads=stats.get("hot_leads", 0),
            warm_leads=stats.get("warm_leads", 0),
            cold_leads=stats.get("cold_leads", 0),
            leads_contacted=stats.get("leads_contacted", 0),
            leads_converted=stats.get("leads_converted", 0),
            conversion_rate=stats.get("conversion_rate", 0.0),
            avg_intent_score=stats.get("avg_intent_score", 0.0)
        )

    # ============================================
    # Public Sponsor Queries (for attendees)
    # ============================================

    def public_event_sponsors(
        self, event_id: str, info: Info
    ) -> List[SponsorType]:
        """Get public sponsor list for an event (attendee view)."""
        db = info.context.db

        # Verify event exists and is public
        event = crud.event.get(db, id=event_id)
        if not event or not event.is_public or event.is_archived:
            raise HTTPException(status_code=404, detail="Event not found")

        sponsors = crud.sponsor.get_by_event(
            db,
            event_id=event_id,
            include_archived=False
        )

        # Only return active sponsors
        return [s for s in sponsors if s.is_active]

    def public_sponsor(
        self, sponsor_id: str, info: Info
    ) -> Optional[SponsorType]:
        """Get public sponsor details (attendee view)."""
        db = info.context.db

        sponsor = crud.sponsor.get(db, id=sponsor_id)
        if not sponsor or not sponsor.is_active or sponsor.is_archived:
            return None

        # Verify event is public
        event = crud.event.get(db, id=sponsor.event_id)
        if not event or not event.is_public or event.is_archived:
            return None

        return sponsor
