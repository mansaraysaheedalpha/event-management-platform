# app/api/v1/endpoints/venue_spaces.py
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status, Response
from sqlalchemy.orm import Session

from app.api import deps
from app.db.session import get_db
from app.crud.crud_venue import venue as crud_venue_obj
from app.crud.crud_venue_space import venue_space as crud_space
from app.schemas.venue_space import (
    VenueSpace,
    VenueSpaceCreate,
    VenueSpaceUpdate,
    VenueSpacePricing,
    SpacePricingSet,
)
from app.schemas.token import TokenPayload

router = APIRouter(tags=["Venue Spaces"])


def _verify_venue_ownership(
    db: Session, org_id: str, venue_id: str
):
    """Verify the venue exists and belongs to the org."""
    venue = crud_venue_obj.get(db, id=venue_id)
    if not venue or venue.organization_id != org_id or venue.is_archived:
        raise HTTPException(status_code=404, detail="Venue not found")
    return venue


@router.post(
    "/organizations/{orgId}/venues/{venueId}/spaces",
    response_model=VenueSpace,
    status_code=status.HTTP_201_CREATED,
)
def create_space(
    orgId: str,
    venueId: str,
    space_in: VenueSpaceCreate,
    db: Session = Depends(get_db),
    current_user: TokenPayload = Depends(deps.get_current_user),
):
    """Add a space to a venue."""
    if current_user.org_id != orgId:
        raise HTTPException(status_code=403, detail="Not authorized")
    _verify_venue_ownership(db, orgId, venueId)
    space = crud_space.create(db, venue_id=venueId, obj_in=space_in.model_dump())
    crud_venue_obj.recompute_total_capacity(db, venue_id=venueId)
    return space


@router.get(
    "/organizations/{orgId}/venues/{venueId}/spaces",
    response_model=List[VenueSpace],
)
def list_spaces(
    orgId: str,
    venueId: str,
    db: Session = Depends(get_db),
    current_user: TokenPayload = Depends(deps.get_current_user),
):
    """List all spaces for a venue."""
    if current_user.org_id != orgId:
        raise HTTPException(status_code=403, detail="Not authorized")
    _verify_venue_ownership(db, orgId, venueId)
    return crud_space.get_multi_by_venue(db, venue_id=venueId)


@router.patch(
    "/organizations/{orgId}/venues/{venueId}/spaces/{spaceId}",
    response_model=VenueSpace,
)
def update_space(
    orgId: str,
    venueId: str,
    spaceId: str,
    space_in: VenueSpaceUpdate,
    db: Session = Depends(get_db),
    current_user: TokenPayload = Depends(deps.get_current_user),
):
    """Update a space."""
    if current_user.org_id != orgId:
        raise HTTPException(status_code=403, detail="Not authorized")
    _verify_venue_ownership(db, orgId, venueId)
    space = crud_space.get(db, id=spaceId)
    if not space or space.venue_id != venueId:
        raise HTTPException(status_code=404, detail="Space not found")
    updated = crud_space.update(
        db, db_obj=space, obj_in=space_in.model_dump(exclude_unset=True)
    )
    if space_in.capacity is not None:
        crud_venue_obj.recompute_total_capacity(db, venue_id=venueId)
    return updated


@router.delete(
    "/organizations/{orgId}/venues/{venueId}/spaces/{spaceId}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_space(
    orgId: str,
    venueId: str,
    spaceId: str,
    db: Session = Depends(get_db),
    current_user: TokenPayload = Depends(deps.get_current_user),
):
    """Delete a space."""
    if current_user.org_id != orgId:
        raise HTTPException(status_code=403, detail="Not authorized")
    _verify_venue_ownership(db, orgId, venueId)
    space = crud_space.get(db, id=spaceId)
    if not space or space.venue_id != venueId:
        raise HTTPException(status_code=404, detail="Space not found")
    crud_space.delete(db, id=spaceId)
    crud_venue_obj.recompute_total_capacity(db, venue_id=venueId)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.put(
    "/organizations/{orgId}/venues/{venueId}/spaces/{spaceId}/pricing",
    response_model=List[VenueSpacePricing],
)
def set_space_pricing(
    orgId: str,
    venueId: str,
    spaceId: str,
    pricing_in: SpacePricingSet,
    db: Session = Depends(get_db),
    current_user: TokenPayload = Depends(deps.get_current_user),
):
    """Set/replace all pricing for a space (idempotent)."""
    if current_user.org_id != orgId:
        raise HTTPException(status_code=403, detail="Not authorized")
    _verify_venue_ownership(db, orgId, venueId)
    space = crud_space.get(db, id=spaceId)
    if not space or space.venue_id != venueId:
        raise HTTPException(status_code=404, detail="Space not found")
    return crud_space.set_pricing(
        db,
        space_id=spaceId,
        pricing_items=[p.model_dump() for p in pricing_in.pricing],
    )
