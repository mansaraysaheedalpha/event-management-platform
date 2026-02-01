# app/api/v1/endpoints/sponsor_user_settings.py
"""
Sponsor user settings endpoints.

Allows users to manage their own profile and preferences within a sponsor account.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import Any

from app.api import deps
from app.schemas.token import TokenPayload
from app.schemas.sponsor import (
    SponsorUserProfileUpdate,
    SponsorUserPreferencesUpdate,
    SponsorUserResponse,
)
from app.crud import sponsor_user
from app.db.session import get_db
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get(
    "/sponsors/{sponsor_id}/settings/profile",
    response_model=SponsorUserResponse
)
def get_user_profile(
    sponsor_id: str,
    *,
    db: Session = Depends(get_db),
    current_user: TokenPayload = Depends(deps.get_current_user),
) -> Any:
    """
    Get current user's profile settings for a sponsor.

    Returns the user's profile information including job title and preferences.
    """
    # Get user's sponsor relationship
    su = sponsor_user.get_by_user_and_sponsor(
        db, user_id=current_user.sub, sponsor_id=sponsor_id
    )

    if not su or not su.is_active:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User profile not found for this sponsor"
        )

    return su


@router.put(
    "/sponsors/{sponsor_id}/settings/profile",
    response_model=SponsorUserResponse
)
def update_user_profile(
    sponsor_id: str,
    profile_update: SponsorUserProfileUpdate,
    *,
    db: Session = Depends(get_db),
    current_user: TokenPayload = Depends(deps.get_current_user),
) -> Any:
    """
    Update current user's profile settings.

    Allows users to update their job title within the sponsor organization.
    """
    # Get user's sponsor relationship
    su = sponsor_user.get_by_user_and_sponsor(
        db, user_id=current_user.sub, sponsor_id=sponsor_id
    )

    if not su or not su.is_active:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User profile not found for this sponsor"
        )

    # Update profile fields
    if profile_update.job_title is not None:
        su.job_title = profile_update.job_title

    db.commit()
    db.refresh(su)

    logger.info(f"User {current_user.sub} updated profile for sponsor {sponsor_id}")

    return su


@router.put(
    "/sponsors/{sponsor_id}/settings/preferences",
    response_model=SponsorUserResponse
)
def update_user_preferences(
    sponsor_id: str,
    preferences_update: SponsorUserPreferencesUpdate,
    *,
    db: Session = Depends(get_db),
    current_user: TokenPayload = Depends(deps.get_current_user),
) -> Any:
    """
    Update current user's notification preferences.

    Allows users to customize which notifications they receive.
    """
    # Get user's sponsor relationship
    su = sponsor_user.get_by_user_and_sponsor(
        db, user_id=current_user.sub, sponsor_id=sponsor_id
    )

    if not su or not su.is_active:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User profile not found for this sponsor"
        )

    # Update preference fields
    update_data = preferences_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(su, field, value)

    db.commit()
    db.refresh(su)

    logger.info(f"User {current_user.sub} updated preferences for sponsor {sponsor_id}")

    return su
