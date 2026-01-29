# app/crud/crud_sponsor.py
"""
CRUD operations for sponsor management.
"""

from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_, func
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone, timedelta
import secrets

from .base import CRUDBase
from app.models.sponsor_tier import SponsorTier
from app.models.sponsor import Sponsor
from app.models.sponsor_user import SponsorUser
from app.models.sponsor_invitation import SponsorInvitation
from app.models.sponsor_lead import SponsorLead
from app.models.sponsor_lead_stats_cache import SponsorLeadStatsCache
from app.schemas.sponsor import (
    SponsorTierCreate, SponsorTierUpdate,
    SponsorCreate, SponsorUpdate,
    SponsorUserCreate, SponsorUserUpdate,
    SponsorInvitationCreate,
    SponsorLeadCreate, SponsorLeadUpdate,
)


# ============================================
# Sponsor Tier CRUD
# ============================================

class CRUDSponsorTier(CRUDBase[SponsorTier, SponsorTierCreate, SponsorTierUpdate]):
    def get_by_event(
        self,
        db: Session,
        *,
        event_id: str,
        active_only: bool = True
    ) -> List[SponsorTier]:
        """Get all sponsor tiers for an event, ordered by display_order."""
        query = db.query(self.model).filter(self.model.event_id == event_id)
        if active_only:
            query = query.filter(self.model.is_active == True)
        return query.order_by(self.model.display_order).all()

    def create_tier(
        self,
        db: Session,
        *,
        tier_in: SponsorTierCreate,
        event_id: str,
        organization_id: str
    ) -> SponsorTier:
        """Create a new sponsor tier for an event."""
        db_obj = self.model(
            event_id=event_id,
            organization_id=organization_id,
            name=tier_in.name,
            display_order=tier_in.display_order,
            color=tier_in.color,
            benefits=tier_in.benefits,
            booth_size=tier_in.booth_size,
            logo_placement=tier_in.logo_placement,
            max_representatives=tier_in.max_representatives,
            can_capture_leads=tier_in.can_capture_leads,
            can_export_leads=tier_in.can_export_leads,
            can_send_messages=tier_in.can_send_messages,
            price_cents=tier_in.price_cents,
            currency=tier_in.currency,
        )
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def create_default_tiers(
        self,
        db: Session,
        *,
        event_id: str,
        organization_id: str
    ) -> List[SponsorTier]:
        """Create default sponsor tiers (Platinum, Gold, Silver, Bronze) for an event."""
        default_tiers = [
            {
                "name": "Platinum",
                "display_order": 1,
                "color": "#E5E4E2",
                "benefits": [
                    "Premium logo placement on all event materials",
                    "Large booth space (10x10)",
                    "Speaking opportunity at main stage",
                    "Access to all attendee data",
                    "5 VIP passes",
                    "Social media promotion"
                ],
                "booth_size": "large",
                "logo_placement": "header",
                "max_representatives": 10,
                "can_capture_leads": True,
                "can_export_leads": True,
                "can_send_messages": True,
            },
            {
                "name": "Gold",
                "display_order": 2,
                "color": "#FFD700",
                "benefits": [
                    "Logo on event website and materials",
                    "Medium booth space (8x8)",
                    "Workshop session opportunity",
                    "Lead capture access",
                    "3 VIP passes"
                ],
                "booth_size": "medium",
                "logo_placement": "sidebar",
                "max_representatives": 5,
                "can_capture_leads": True,
                "can_export_leads": True,
                "can_send_messages": False,
            },
            {
                "name": "Silver",
                "display_order": 3,
                "color": "#C0C0C0",
                "benefits": [
                    "Logo on event website",
                    "Standard booth space (6x6)",
                    "Lead capture access",
                    "2 VIP passes"
                ],
                "booth_size": "small",
                "logo_placement": "footer",
                "max_representatives": 3,
                "can_capture_leads": True,
                "can_export_leads": False,
                "can_send_messages": False,
            },
            {
                "name": "Bronze",
                "display_order": 4,
                "color": "#CD7F32",
                "benefits": [
                    "Logo on event website",
                    "Table space",
                    "1 pass"
                ],
                "booth_size": "table",
                "logo_placement": "footer",
                "max_representatives": 2,
                "can_capture_leads": True,
                "can_export_leads": False,
                "can_send_messages": False,
            },
        ]

        created_tiers = []
        for tier_data in default_tiers:
            db_obj = self.model(
                event_id=event_id,
                organization_id=organization_id,
                **tier_data
            )
            db.add(db_obj)
            created_tiers.append(db_obj)

        db.commit()
        for tier in created_tiers:
            db.refresh(tier)

        return created_tiers


# ============================================
# Sponsor CRUD
# ============================================

class CRUDSponsor(CRUDBase[Sponsor, SponsorCreate, SponsorUpdate]):
    def get_by_event(
        self,
        db: Session,
        *,
        event_id: str,
        include_archived: bool = False,
        include_tier: bool = False
    ) -> List[Sponsor]:
        """Get all sponsors for an event."""
        query = db.query(self.model).filter(self.model.event_id == event_id)

        if not include_archived:
            query = query.filter(self.model.is_archived == False)

        if include_tier:
            query = query.options(joinedload(self.model.tier))

        return query.order_by(self.model.is_featured.desc(), self.model.company_name).all()

    def get_with_tier(self, db: Session, *, sponsor_id: str) -> Optional[Sponsor]:
        """Get a sponsor with its tier information."""
        return db.query(self.model).options(
            joinedload(self.model.tier)
        ).filter(self.model.id == sponsor_id).first()

    def create_sponsor(
        self,
        db: Session,
        *,
        sponsor_in: SponsorCreate,
        event_id: str,
        organization_id: str
    ) -> Sponsor:
        """Create a new sponsor for an event."""
        db_obj = self.model(
            event_id=event_id,
            organization_id=organization_id,
            tier_id=sponsor_in.tier_id,
            company_name=sponsor_in.company_name,
            company_description=sponsor_in.company_description,
            company_website=sponsor_in.company_website,
            company_logo_url=sponsor_in.company_logo_url,
            contact_name=sponsor_in.contact_name,
            contact_email=sponsor_in.contact_email,
            contact_phone=sponsor_in.contact_phone,
            booth_number=sponsor_in.booth_number,
            booth_description=sponsor_in.booth_description,
            custom_booth_url=sponsor_in.custom_booth_url,
            social_links=sponsor_in.social_links or {},
            marketing_assets=sponsor_in.marketing_assets or [],
            lead_capture_enabled=sponsor_in.lead_capture_enabled,
            lead_notification_email=sponsor_in.lead_notification_email,
            custom_fields=sponsor_in.custom_fields or {},
        )
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def get_by_user(
        self,
        db: Session,
        *,
        user_id: str,
        event_id: Optional[str] = None
    ) -> List[Sponsor]:
        """Get all sponsors that a user is associated with."""
        query = db.query(self.model).join(
            SponsorUser, SponsorUser.sponsor_id == self.model.id
        ).filter(
            SponsorUser.user_id == user_id,
            SponsorUser.is_active == True,
            self.model.is_archived == False
        )

        if event_id:
            query = query.filter(self.model.event_id == event_id)

        return query.all()


# ============================================
# Sponsor User CRUD
# ============================================

class CRUDSponsorUser(CRUDBase[SponsorUser, SponsorUserCreate, SponsorUserUpdate]):
    def get_by_sponsor(
        self,
        db: Session,
        *,
        sponsor_id: str,
        active_only: bool = True
    ) -> List[SponsorUser]:
        """Get all users for a sponsor."""
        query = db.query(self.model).filter(self.model.sponsor_id == sponsor_id)
        if active_only:
            query = query.filter(self.model.is_active == True)
        return query.order_by(self.model.joined_at).all()

    def get_by_user_and_sponsor(
        self,
        db: Session,
        *,
        user_id: str,
        sponsor_id: str
    ) -> Optional[SponsorUser]:
        """Get a specific user-sponsor relationship."""
        return db.query(self.model).filter(
            self.model.user_id == user_id,
            self.model.sponsor_id == sponsor_id
        ).first()

    def create_sponsor_user(
        self,
        db: Session,
        *,
        user_in: SponsorUserCreate,
        sponsor_id: str
    ) -> SponsorUser:
        """Add a user to a sponsor."""
        db_obj = self.model(
            sponsor_id=sponsor_id,
            user_id=user_in.user_id,
            role=user_in.role,
            can_view_leads=user_in.can_view_leads,
            can_export_leads=user_in.can_export_leads,
            can_message_attendees=user_in.can_message_attendees,
            can_manage_booth=user_in.can_manage_booth,
            can_invite_others=user_in.can_invite_others,
        )
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def update_last_active(
        self,
        db: Session,
        *,
        sponsor_user_id: str
    ) -> Optional[SponsorUser]:
        """Update the last_active_at timestamp."""
        sponsor_user = self.get(db, id=sponsor_user_id)
        if sponsor_user:
            sponsor_user.last_active_at = datetime.now(timezone.utc)
            db.commit()
            db.refresh(sponsor_user)
        return sponsor_user

    def count_by_sponsor(self, db: Session, *, sponsor_id: str) -> int:
        """Count active users for a sponsor."""
        return db.query(func.count(self.model.id)).filter(
            self.model.sponsor_id == sponsor_id,
            self.model.is_active == True
        ).scalar()


# ============================================
# Sponsor Invitation CRUD
# ============================================

class CRUDSponsorInvitation(CRUDBase[SponsorInvitation, SponsorInvitationCreate, SponsorInvitationCreate]):
    def get_by_token(self, db: Session, *, token: str) -> Optional[SponsorInvitation]:
        """Get an invitation by its token."""
        return db.query(self.model).filter(self.model.token == token).first()

    def get_by_sponsor(
        self,
        db: Session,
        *,
        sponsor_id: str,
        status: Optional[str] = None
    ) -> List[SponsorInvitation]:
        """Get all invitations for a sponsor."""
        query = db.query(self.model).filter(self.model.sponsor_id == sponsor_id)
        if status:
            query = query.filter(self.model.status == status)
        return query.order_by(self.model.created_at.desc()).all()

    def get_pending_by_email(
        self,
        db: Session,
        *,
        email: str,
        sponsor_id: str
    ) -> Optional[SponsorInvitation]:
        """Check if there's already a pending invitation for this email."""
        return db.query(self.model).filter(
            self.model.email == email,
            self.model.sponsor_id == sponsor_id,
            self.model.status == 'pending'
        ).first()

    def create_invitation(
        self,
        db: Session,
        *,
        invitation_in: SponsorInvitationCreate,
        sponsor_id: str,
        invited_by_user_id: str,
        expiry_days: int = 7
    ) -> SponsorInvitation:
        """Create a new sponsor invitation."""
        db_obj = self.model(
            sponsor_id=sponsor_id,
            email=invitation_in.email,
            token=secrets.token_urlsafe(32),
            role=invitation_in.role,
            can_view_leads=invitation_in.can_view_leads,
            can_export_leads=invitation_in.can_export_leads,
            can_message_attendees=invitation_in.can_message_attendees,
            can_manage_booth=invitation_in.can_manage_booth,
            can_invite_others=invitation_in.can_invite_others,
            invited_by_user_id=invited_by_user_id,
            personal_message=invitation_in.personal_message,
            expires_at=datetime.now(timezone.utc) + timedelta(days=expiry_days),
        )
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def accept_invitation(
        self,
        db: Session,
        *,
        invitation: SponsorInvitation,
        user_id: str
    ) -> SponsorInvitation:
        """Mark an invitation as accepted."""
        invitation.status = 'accepted'
        invitation.accepted_by_user_id = user_id
        invitation.accepted_at = datetime.now(timezone.utc)
        invitation.updated_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(invitation)
        return invitation

    def revoke_invitation(
        self,
        db: Session,
        *,
        invitation_id: str
    ) -> Optional[SponsorInvitation]:
        """Revoke a pending invitation."""
        invitation = self.get(db, id=invitation_id)
        if invitation and invitation.status == 'pending':
            invitation.status = 'revoked'
            invitation.updated_at = datetime.now(timezone.utc)
            db.commit()
            db.refresh(invitation)
        return invitation

    def expire_old_invitations(self, db: Session) -> int:
        """Background task: Mark expired invitations."""
        now = datetime.now(timezone.utc)
        result = db.query(self.model).filter(
            self.model.status == 'pending',
            self.model.expires_at < now
        ).update({"status": "expired", "updated_at": now})
        db.commit()
        return result


# ============================================
# Sponsor Lead CRUD
# ============================================

class CRUDSponsorLead(CRUDBase[SponsorLead, SponsorLeadCreate, SponsorLeadUpdate]):
    # Scoring weights for different interaction types
    # Higher scores indicate higher purchase intent
    INTERACTION_SCORES = {
        # Booth interactions
        'booth_visit': 10,
        'booth_contact_form': 25,  # Filling out contact form shows intent
        'repeat_visit': 5,  # Bonus for returning visitors

        # Content engagement
        'content_download': 15,  # Downloaded a resource
        'content_view': 5,       # Viewed content (passive)

        # High-intent actions
        'demo_watched': 20,      # Watched a demo video to completion
        'demo_request': 30,      # Explicitly requested a demo
        'direct_request': 35,    # Direct contact request
        'cta_click': 10,         # Clicked a call-to-action button

        # Other interactions
        'qr_scan': 10,           # Scanned booth QR code
        'session_attendance': 15, # Attended sponsor session
        'video_session': 8,      # Started video (not completed)
        'chat_message': 12,      # Sent a chat message
    }

    def get_by_sponsor(
        self,
        db: Session,
        *,
        sponsor_id: str,
        intent_level: Optional[str] = None,
        include_archived: bool = False,
        skip: int = 0,
        limit: int = 100
    ) -> List[SponsorLead]:
        """Get all leads for a sponsor with optional filtering."""
        query = db.query(self.model).filter(self.model.sponsor_id == sponsor_id)

        if not include_archived:
            query = query.filter(self.model.is_archived == False)

        if intent_level:
            query = query.filter(self.model.intent_level == intent_level)

        return query.order_by(
            self.model.intent_score.desc(),
            self.model.last_interaction_at.desc()
        ).offset(skip).limit(limit).all()

    def get_by_user_and_sponsor(
        self,
        db: Session,
        *,
        user_id: str,
        sponsor_id: str
    ) -> Optional[SponsorLead]:
        """Get a lead by user and sponsor (for upsert operations)."""
        return db.query(self.model).filter(
            self.model.user_id == user_id,
            self.model.sponsor_id == sponsor_id
        ).first()

    def capture_lead(
        self,
        db: Session,
        *,
        lead_in: SponsorLeadCreate,
        sponsor_id: str,
        event_id: str
    ) -> SponsorLead:
        """
        Capture a new lead or update existing one with new interaction.
        This is the main method called when an attendee interacts with a sponsor.
        """
        # Check if lead already exists
        existing_lead = self.get_by_user_and_sponsor(
            db, user_id=lead_in.user_id, sponsor_id=sponsor_id
        )

        interaction = {
            'type': lead_in.interaction_type,
            'timestamp': datetime.now(timezone.utc).isoformat(),
            **(lead_in.interaction_metadata or {})
        }

        if existing_lead:
            # Update existing lead
            existing_lead.interaction_count += 1
            existing_lead.last_interaction_at = datetime.now(timezone.utc)

            # Add new interaction to history
            interactions = existing_lead.interactions or []
            interactions.insert(0, interaction)
            existing_lead.interactions = interactions[:50]  # Keep last 50 interactions

            # Update score
            score_increase = self.INTERACTION_SCORES.get(lead_in.interaction_type, 5)
            if existing_lead.interaction_count > 1:
                score_increase += self.INTERACTION_SCORES.get('repeat_visit', 5)

            existing_lead.intent_score = min(100, existing_lead.intent_score + score_increase)
            existing_lead.intent_level = self._calculate_intent_level(existing_lead.intent_score)
            existing_lead.updated_at = datetime.now(timezone.utc)

            db.commit()
            db.refresh(existing_lead)
            return existing_lead

        # Create new lead
        initial_score = self.INTERACTION_SCORES.get(lead_in.interaction_type, 10)
        intent_level = self._calculate_intent_level(initial_score)

        db_obj = self.model(
            sponsor_id=sponsor_id,
            event_id=event_id,
            user_id=lead_in.user_id,
            user_name=lead_in.user_name,
            user_email=lead_in.user_email,
            user_company=lead_in.user_company,
            user_title=lead_in.user_title,
            intent_score=initial_score,
            intent_level=intent_level,
            interactions=[interaction],
        )
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def _calculate_intent_level(self, score: int) -> str:
        """Calculate intent level based on score."""
        if score >= 70:
            return 'hot'
        elif score >= 40:
            return 'warm'
        return 'cold'

    def update_follow_up(
        self,
        db: Session,
        *,
        lead_id: str,
        status: str,
        notes: Optional[str] = None,
        user_id: str
    ) -> Optional[SponsorLead]:
        """Update the follow-up status of a lead."""
        lead = self.get(db, id=lead_id)
        if lead:
            lead.follow_up_status = status
            lead.follow_up_notes = notes
            lead.followed_up_at = datetime.now(timezone.utc)
            lead.followed_up_by_user_id = user_id
            lead.updated_at = datetime.now(timezone.utc)
            db.commit()
            db.refresh(lead)
        return lead

    def get_stats(self, db: Session, *, sponsor_id: str) -> Dict[str, Any]:
        """
        Get lead statistics for a sponsor.

        First tries the pre-computed cache (updated by PostgreSQL trigger),
        then falls back to live aggregation if cache is not available.
        """
        # Try to get from cache first (O(1) lookup)
        cached_stats = db.query(SponsorLeadStatsCache).filter(
            SponsorLeadStatsCache.sponsor_id == sponsor_id
        ).first()

        if cached_stats:
            return cached_stats.to_dict()

        # Fallback to live aggregation (for sponsors without any leads yet)
        leads = db.query(self.model).filter(
            self.model.sponsor_id == sponsor_id,
            self.model.is_archived == False
        ).all()

        total = len(leads)
        hot = sum(1 for l in leads if l.intent_level == 'hot')
        warm = sum(1 for l in leads if l.intent_level == 'warm')
        cold = sum(1 for l in leads if l.intent_level == 'cold')
        contacted = sum(1 for l in leads if l.follow_up_status != 'new')
        converted = sum(1 for l in leads if l.follow_up_status == 'converted')
        avg_score = sum(l.intent_score for l in leads) / total if total > 0 else 0

        return {
            'total_leads': total,
            'hot_leads': hot,
            'warm_leads': warm,
            'cold_leads': cold,
            'leads_contacted': contacted,
            'leads_converted': converted,
            'conversion_rate': (converted / total * 100) if total > 0 else 0,
            'avg_intent_score': round(avg_score, 1),
        }


# Create singleton instances
sponsor_tier = CRUDSponsorTier(SponsorTier)
sponsor = CRUDSponsor(Sponsor)
sponsor_user = CRUDSponsorUser(SponsorUser)
sponsor_invitation = CRUDSponsorInvitation(SponsorInvitation)
sponsor_lead = CRUDSponsorLead(SponsorLead)
