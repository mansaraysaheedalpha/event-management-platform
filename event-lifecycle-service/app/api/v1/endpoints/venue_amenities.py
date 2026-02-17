# app/api/v1/endpoints/venue_amenities.py
from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api import deps
from app.db.session import get_db
from app.crud.crud_venue import venue as crud_venue_obj
from app.crud.crud_amenity import amenity as crud_amenity_obj
from app.schemas.amenity import VenueAmenitySet, VenueAmenityResolved
from app.schemas.token import TokenPayload

router = APIRouter(tags=["Venue Amenities"])


@router.put(
    "/organizations/{orgId}/venues/{venueId}/amenities",
    response_model=List[VenueAmenityResolved],
)
def set_venue_amenities(
    orgId: str,
    venueId: str,
    amenity_set: VenueAmenitySet,
    db: Session = Depends(get_db),
    current_user: TokenPayload = Depends(deps.get_current_user),
):
    """Set/replace all amenities for a venue (idempotent)."""
    if current_user.org_id != orgId:
        raise HTTPException(status_code=403, detail="Not authorized")

    venue = crud_venue_obj.get(db, id=venueId)
    if not venue or venue.organization_id != orgId or venue.is_archived:
        raise HTTPException(status_code=404, detail="Venue not found")

    return crud_amenity_obj.set_venue_amenities(
        db,
        venue_id=venueId,
        amenity_items=[a.model_dump() for a in amenity_set.amenities],
    )
