# app/graphql/ad_mutations.py
"""
GraphQL mutations for Ad management.

Provides mutation endpoints for:
- Creating ads
- Updating ads
- Deleting/archiving ads
- Tracking ad impressions and clicks
"""
import strawberry
from typing import Optional, List
from strawberry.types import Info
from fastapi import HTTPException
from datetime import datetime, timezone
import uuid
import logging

from .. import crud
from ..models.ad import Ad
from ..crud.crud_ad_event import ad_event
from ..schemas.ad import AdCreateDTO, AdUpdateDTO, ContentType, ImpressionTrackingDTO
from .types import AdType
from ..utils.security import (
    validate_ad_input,
    validate_url,
    validate_array_size,
    validate_string_length,
    validate_enum,
    sanitize_error_message,
    MAX_ARRAY_SIZES,
    VALID_PLACEMENTS,
)

logger = logging.getLogger(__name__)


# Input Types
@strawberry.input
class AdCreateInput:
    """Input for creating a new ad."""
    event_id: str
    name: str
    content_type: str  # BANNER, VIDEO, SPONSORED_SESSION, INTERSTITIAL
    media_url: str
    click_url: str
    display_duration_seconds: Optional[int] = 30
    aspect_ratio: Optional[str] = "16:9"
    starts_at: Optional[str] = None  # ISO datetime string
    ends_at: Optional[str] = None  # ISO datetime string
    placements: Optional[List[str]] = None  # EVENT_HERO, SESSION_BREAK, etc.
    target_sessions: Optional[List[str]] = None
    weight: Optional[int] = 1
    frequency_cap: Optional[int] = 3
    is_active: Optional[bool] = True


@strawberry.input
class AdUpdateInput:
    """Input for updating an existing ad."""
    name: Optional[str] = None
    media_url: Optional[str] = None
    click_url: Optional[str] = None
    display_duration_seconds: Optional[int] = None
    aspect_ratio: Optional[str] = None
    starts_at: Optional[str] = None
    ends_at: Optional[str] = None
    placements: Optional[List[str]] = None
    target_sessions: Optional[List[str]] = None
    weight: Optional[int] = None
    frequency_cap: Optional[int] = None
    is_active: Optional[bool] = None


@strawberry.input
class AdImpressionInput:
    """Input for tracking an ad impression."""
    ad_id: str
    context: Optional[str] = None  # Session context
    viewable_duration_ms: Optional[int] = 0
    viewport_percentage: Optional[int] = 100


@strawberry.type
class AdTrackingResult:
    """Result of ad tracking operations."""
    success: bool
    trackedCount: int
    message: Optional[str] = None


@strawberry.type
class AdClickResult:
    """Result of ad click tracking."""
    success: bool
    redirectUrl: Optional[str] = None


def _convert_ad_to_type(ad: Ad) -> Ad:
    """Return Ad model - Strawberry will use AdType resolvers to map fields."""
    return ad


class AdMutations:
    """Ad mutation resolvers - helper methods called from main Mutation class"""

    def create_ad(self, ad_in: AdCreateInput, info: Info) -> AdType:
        """
        Create a new ad for an event.

        Requires authentication and organizer access to the event.
        """
        user = info.context.user
        if not user:
            raise HTTPException(status_code=401, detail="Authentication required")

        db = info.context.db
        org_id = user.get("orgId")

        if not org_id:
            raise HTTPException(status_code=403, detail="Organization membership required")

        # Verify event ownership
        event = crud.event.get(db, id=ad_in.event_id)
        if not event:
            raise HTTPException(status_code=404, detail="Event not found")

        if event.organization_id != org_id:
            raise HTTPException(
                status_code=403,
                detail="Not authorized to create ads for this event"
            )

        # SECURITY: Validate all input fields
        validation_errors = validate_ad_input(ad_in)
        if validation_errors:
            raise HTTPException(
                status_code=400,
                detail=f"Validation failed: {'; '.join(validation_errors)}"
            )

        # Parse content type
        try:
            content_type = ContentType(ad_in.content_type)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid content_type. Must be one of: BANNER, VIDEO, SPONSORED_SESSION, INTERSTITIAL"
            )

        # Parse dates
        starts_at = None
        ends_at = None
        if ad_in.starts_at:
            starts_at = datetime.fromisoformat(ad_in.starts_at.replace("Z", "+00:00"))
        if ad_in.ends_at:
            ends_at = datetime.fromisoformat(ad_in.ends_at.replace("Z", "+00:00"))

        # Build DTO
        ad_dto = AdCreateDTO(
            event_id=ad_in.event_id,
            name=ad_in.name,
            content_type=content_type,
            media_url=ad_in.media_url,
            click_url=ad_in.click_url,
            display_duration_seconds=ad_in.display_duration_seconds or 30,
            aspect_ratio=ad_in.aspect_ratio or "16:9",
            placements=ad_in.placements or ["EVENT_HERO"],
            target_sessions=ad_in.target_sessions or [],
            weight=ad_in.weight or 1,
            frequency_cap=ad_in.frequency_cap or 3,
            starts_at=starts_at,
            ends_at=ends_at,
        )

        # Create ad using CRUD
        ad = crud.ad.create_ad(db, ad_data=ad_dto, organization_id=org_id)

        return _convert_ad_to_type(ad)

    def update_ad(self, id: str, ad_in: AdUpdateInput, info: Info) -> AdType:
        """
        Update an existing ad.

        Requires authentication and organizer access.
        """
        user = info.context.user
        if not user:
            raise HTTPException(status_code=401, detail="Authentication required")

        db = info.context.db
        org_id = user.get("orgId")

        if not org_id:
            raise HTTPException(status_code=403, detail="Organization membership required")

        # Get existing ad
        ad = crud.ad.get(db, id=id)
        if not ad:
            raise HTTPException(status_code=404, detail="Ad not found")

        if ad.organization_id != org_id:
            raise HTTPException(status_code=403, detail="Not authorized to update this ad")

        # SECURITY: Validate URLs if provided
        if ad_in.media_url is not None:
            valid, err = validate_url(ad_in.media_url, "media_url", allow_http=True)
            if not valid:
                raise HTTPException(status_code=400, detail=err)

        if ad_in.click_url is not None:
            valid, err = validate_url(ad_in.click_url, "click_url", allow_http=False, allow_redirects=True)
            if not valid:
                raise HTTPException(status_code=400, detail=err)

        # SECURITY: Validate string lengths
        if ad_in.name is not None:
            valid, err = validate_string_length(ad_in.name, "name")
            if not valid:
                raise HTTPException(status_code=400, detail=err)

        # SECURITY: Validate array sizes and placement values
        if ad_in.placements is not None:
            valid, err = validate_array_size(ad_in.placements, "placements")
            if not valid:
                raise HTTPException(status_code=400, detail=err)
            for p in ad_in.placements:
                valid, err = validate_enum(p, "placement", VALID_PLACEMENTS)
                if not valid:
                    raise HTTPException(status_code=400, detail=err)

        if ad_in.target_sessions is not None:
            valid, err = validate_array_size(ad_in.target_sessions, "target_sessions")
            if not valid:
                raise HTTPException(status_code=400, detail=err)

        # Build update DTO
        update_kwargs = {}
        if ad_in.name is not None:
            update_kwargs["name"] = ad_in.name
        if ad_in.media_url is not None:
            update_kwargs["media_url"] = ad_in.media_url
        if ad_in.click_url is not None:
            update_kwargs["click_url"] = ad_in.click_url
        if ad_in.display_duration_seconds is not None:
            update_kwargs["display_duration_seconds"] = ad_in.display_duration_seconds
        if ad_in.aspect_ratio is not None:
            update_kwargs["aspect_ratio"] = ad_in.aspect_ratio
        if ad_in.starts_at is not None:
            update_kwargs["starts_at"] = datetime.fromisoformat(ad_in.starts_at.replace("Z", "+00:00"))
        if ad_in.ends_at is not None:
            update_kwargs["ends_at"] = datetime.fromisoformat(ad_in.ends_at.replace("Z", "+00:00"))
        if ad_in.placements is not None:
            update_kwargs["placements"] = ad_in.placements
        if ad_in.target_sessions is not None:
            update_kwargs["target_sessions"] = ad_in.target_sessions
        if ad_in.weight is not None:
            update_kwargs["weight"] = ad_in.weight
        if ad_in.frequency_cap is not None:
            update_kwargs["frequency_cap"] = ad_in.frequency_cap
        if ad_in.is_active is not None:
            update_kwargs["is_active"] = ad_in.is_active

        if not update_kwargs:
            return _convert_ad_to_type(ad)

        ad_dto = AdUpdateDTO(**update_kwargs)

        # Update ad using CRUD
        updated_ad = crud.ad.update_ad(db, ad_id=id, ad_data=ad_dto)

        return _convert_ad_to_type(updated_ad)

    def delete_ad(self, id: str, info: Info) -> bool:
        """
        Delete (archive) an ad.

        Requires authentication and organizer access.
        """
        user = info.context.user
        if not user:
            raise HTTPException(status_code=401, detail="Authentication required")

        db = info.context.db
        org_id = user.get("orgId")

        if not org_id:
            raise HTTPException(status_code=403, detail="Organization membership required")

        # Get existing ad
        ad = crud.ad.get(db, id=id)
        if not ad:
            raise HTTPException(status_code=404, detail="Ad not found")

        if ad.organization_id != org_id:
            raise HTTPException(status_code=403, detail="Not authorized to delete this ad")

        # Archive instead of hard delete
        crud.ad.update(db, db_obj=ad, obj_in={"is_archived": True, "is_active": False})

        return True

    def track_ad_impressions(
        self,
        impressions: List[AdImpressionInput],
        info: Info
    ) -> AdTrackingResult:
        """
        Track multiple ad impressions in bulk.

        Rate limited to prevent abuse.
        """
        if not impressions:
            return AdTrackingResult(success=True, trackedCount=0, message="No impressions to track")

        # SECURITY: Limit array size to prevent DoS
        max_impressions = MAX_ARRAY_SIZES.get("impressions", 100)
        if len(impressions) > max_impressions:
            return AdTrackingResult(
                success=False,
                trackedCount=0,
                message=f"Too many impressions. Maximum {max_impressions} allowed per request."
            )

        db = info.context.db
        user = info.context.user
        user_id = user.get("sub") if user else None

        # Generate session token for anonymous tracking
        session_token = str(uuid.uuid4())

        try:
            # SECURITY: Validate context string length for each impression
            for imp in impressions:
                if imp.context and len(imp.context) > 500:
                    return AdTrackingResult(
                        success=False,
                        trackedCount=0,
                        message="Context string too long"
                    )

            # Convert to DTOs
            impression_dtos = [
                ImpressionTrackingDTO(
                    ad_id=imp.ad_id,
                    context=imp.context,
                    viewable_duration_ms=imp.viewable_duration_ms or 0,
                    viewport_percentage=min(max(imp.viewport_percentage or 100, 0), 100)  # Clamp 0-100
                )
                for imp in impressions
            ]

            # Track impressions using CRUD
            tracked = ad_event.track_impressions_batch(
                db,
                impressions=impression_dtos,
                user_id=user_id,
                session_token=session_token,
                user_agent=None,
                ip_address=None
            )

            return AdTrackingResult(
                success=True,
                trackedCount=tracked,
                message=f"Tracked {tracked} of {len(impressions)} impressions"
            )
        except Exception as e:
            # SECURITY: Log the actual error but return sanitized message
            logger.error(f"Error tracking impressions: {e}")
            return AdTrackingResult(
                success=False,
                trackedCount=0,
                message=sanitize_error_message(e)
            )

    def track_ad_click(
        self,
        ad_id: str,
        session_context: Optional[str] = None,
        info: Info = None
    ) -> AdClickResult:
        """
        Track an ad click.

        Returns the redirect URL for the ad.
        """
        # SECURITY: Validate session_context length
        if session_context and len(session_context) > 500:
            return AdClickResult(success=False, redirectUrl=None)

        db = info.context.db
        user = info.context.user
        user_id = user.get("sub") if user else None

        # Generate session token for tracking
        session_token = str(uuid.uuid4())

        # Get ad
        ad = crud.ad.get(db, id=ad_id)
        if not ad:
            return AdClickResult(success=False, redirectUrl=None)

        # SECURITY: Only return URL for active, non-archived ads
        if ad.is_archived or not ad.is_active:
            return AdClickResult(success=False, redirectUrl=None)

        # Track click FIRST (regardless of URL validation)
        try:
            ad_event.track_click(
                db,
                ad_id=ad_id,
                user_id=user_id,
                session_token=session_token,
                context=session_context,
                user_agent=None,
                ip_address=None,
                referer=None
            )
            logger.info(f"Ad click tracked for ad_id={ad_id}")
        except Exception as e:
            logger.error(f"Error tracking ad click: {e}")

        # SECURITY: Validate the redirect URL before returning it
        valid, error_msg = validate_url(ad.click_url, "click_url", allow_http=False, allow_redirects=True)
        if not valid:
            logger.warning(f"Ad {ad_id} has invalid click_url ({error_msg}), click tracked but blocking redirect. URL: {ad.click_url}")
            # Click is tracked but redirect URL is not returned
            return AdClickResult(success=True, redirectUrl=None)

        return AdClickResult(success=True, redirectUrl=ad.click_url)
