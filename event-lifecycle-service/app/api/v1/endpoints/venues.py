# app/api/v1/endpoints/venues.py
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status, Response
from sqlalchemy.orm import Session

from app.api import deps
from app.db.session import get_db
from app.crud import crud_venue
from app.schemas.venue import Venue, VenueCreate, VenueUpdate
from app.schemas.token import TokenPayload

router = APIRouter(tags=["Venues"])


@router.post(
    "/organizations/{orgId}/venues",
    response_model=Venue,
    status_code=status.HTTP_201_CREATED,
)
def create_venue(
    orgId: str,
    venue_in: VenueCreate,
    db: Session = Depends(get_db),
    current_user: TokenPayload = Depends(deps.get_current_user),
):
    """
    Create a new venue for an organization.
    """
    if current_user.org_id != orgId:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized"
        )
    return crud_venue.venue.create_with_organization(db, obj_in=venue_in, org_id=orgId)


@router.get("/organizations/{orgId}/venues", response_model=List[Venue])
def list_venues(
    orgId: str,
    db: Session = Depends(get_db),
    current_user: TokenPayload = Depends(deps.get_current_user),
):
    """
    List all venues for an organization.
    """
    if current_user.org_id != orgId:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized"
        )
    return crud_venue.venue.get_multi_by_organization(db, org_id=orgId)


@router.get("/organizations/{orgId}/venues/{venueId}", response_model=Venue)
def get_venue(
    orgId: str,
    venueId: str,
    db: Session = Depends(get_db),
    current_user: TokenPayload = Depends(deps.get_current_user),
):
    """
    Get a specific venue by ID.
    """
    if current_user.org_id != orgId:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized"
        )

    venue = crud_venue.venue.get(db, id=venueId)
    if not venue or venue.organization_id != orgId:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Venue not found"
        )
    return venue


@router.patch("/organizations/{orgId}/venues/{venueId}", response_model=Venue)
def update_venue(
    orgId: str,
    venueId: str,
    venue_in: VenueUpdate,
    db: Session = Depends(get_db),
    current_user: TokenPayload = Depends(deps.get_current_user),
):
    """
    Update a venue.
    """
    if current_user.org_id != orgId:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized"
        )

    venue = crud_venue.venue.get(db, id=venueId)
    if not venue or venue.organization_id != orgId:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Venue not found"
        )

    return crud_venue.venue.update(db, db_obj=venue, obj_in=venue_in)


@router.delete(
    "/organizations/{orgId}/venues/{venueId}", status_code=status.HTTP_204_NO_CONTENT
)
def delete_venue(
    orgId: str,
    venueId: str,
    db: Session = Depends(get_db),
    current_user: TokenPayload = Depends(deps.get_current_user),
):
    """
    Soft-delete a venue by archiving it.
    """
    if current_user.org_id != orgId:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized"
        )

    venue = crud_venue.venue.get(db, id=venueId)
    if not venue or venue.organization_id != orgId:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Venue not found"
        )

    crud_venue.venue.archive(db, id=venueId)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
