from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func
from typing import List, Optional, Tuple
from datetime import datetime, timezone
import random
from .base import CRUDBase
from app.models.ad import Ad
from app.schemas.ad import AdCreate, AdUpdate, AdCreateDTO, AdUpdateDTO


class CRUDAd(CRUDBase[Ad, AdCreate, AdUpdate]):
    def get_multi_by_event(
        self,
        db: Session,
        *,
        event_id: str,
        active_only: bool = False
    ) -> List[Ad]:
        """Get all ads for an event with optional filtering."""
        query = db.query(self.model).filter(
            self.model.event_id == event_id,
            self.model.is_archived == False
        )

        if active_only:
            query = query.filter(self.model.is_active == True)

        return query.order_by(self.model.created_at.desc()).all()

    def get_active_ads(
        self,
        db: Session,
        *,
        event_id: str,
        placement: str,
        session_id: Optional[str] = None
    ) -> List[Ad]:
        """
        Get currently active ads for serving to attendees.

        Filters by:
        - is_active = true
        - is_archived = false
        - NOW() between starts_at and ends_at
        - placement matches
        - targeting rules (if session_id specified)
        """
        now = datetime.now(timezone.utc)

        query = db.query(self.model).filter(
            self.model.event_id == event_id,
            self.model.is_active == True,
            self.model.is_archived == False,
            self.model.starts_at <= now,
            or_(
                self.model.ends_at == None,
                self.model.ends_at > now
            )
        )

        # Filter ads that have the requested placement
        # Since placements is an array, we need to check if placement is in the array
        query = query.filter(
            func.array_position(self.model.placements, placement) != None
        )

        ads = query.all()

        # Filter by session targeting if session_id provided
        if session_id:
            ads = [
                ad for ad in ads
                if not ad.target_sessions or len(ad.target_sessions) == 0 or session_id in ad.target_sessions
            ]

        return ads

    def select_ads_weighted_random(
        self,
        ads: List[Ad],
        limit: int = 3
    ) -> List[Ad]:
        """
        Select ads using weighted random selection.
        Ads with higher weight are more likely to be selected.
        """
        if not ads:
            return []

        if len(ads) <= limit:
            return ads

        # Extract weights
        weights = [ad.weight for ad in ads]

        # Use random.choices with weights
        selected = random.choices(ads, weights=weights, k=min(limit, len(ads)))

        return selected

    def create_ad(
        self,
        db: Session,
        *,
        ad_data: AdCreateDTO,
        organization_id: str
    ) -> Ad:
        """
        Create a new advertisement.
        """
        db_obj = self.model(
            event_id=ad_data.event_id,
            organization_id=organization_id,
            name=ad_data.name,
            content_type=ad_data.content_type.value,
            media_url=ad_data.media_url,
            click_url=ad_data.click_url,
            display_duration_seconds=ad_data.display_duration_seconds,
            aspect_ratio=ad_data.aspect_ratio,
            placements=ad_data.placements,
            target_sessions=ad_data.target_sessions,
            weight=ad_data.weight,
            frequency_cap=ad_data.frequency_cap,
            starts_at=ad_data.starts_at or datetime.now(timezone.utc),
            ends_at=ad_data.ends_at,
            is_active=True,
            is_archived=False
        )
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def update_ad(
        self,
        db: Session,
        *,
        ad_id: str,
        ad_data: AdUpdateDTO
    ) -> Optional[Ad]:
        """
        Update an existing ad.
        """
        ad = self.get(db, id=ad_id)
        if not ad:
            return None

        update_data = ad_data.model_dump(exclude_unset=True)

        # Convert enum to string if content_type is being updated
        if 'content_type' in update_data and update_data['content_type']:
            update_data['content_type'] = update_data['content_type'].value

        for field, value in update_data.items():
            setattr(ad, field, value)

        ad.updated_at = datetime.now(timezone.utc)

        db.commit()
        db.refresh(ad)
        return ad

    def auto_expire_ads(self, db: Session) -> int:
        """
        Background task: Set is_active = false for expired ads.
        Returns count of expired ads.
        """
        now = datetime.now(timezone.utc)

        result = db.query(self.model).filter(
            self.model.is_active == True,
            self.model.ends_at != None,
            self.model.ends_at < now
        ).update({"is_active": False, "updated_at": now})

        db.commit()
        return result


# Create singleton instance
ad = CRUDAd(Ad)