# app/api/v1/endpoints/venues.py
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Response, Query
from sqlalchemy.orm import Session

from app.api import deps
from app.db.session import get_db
from app.crud import crud_venue
from app.schemas.venue import Venue, VenueCreate, VenueUpdate, VenueSubmitResponse
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
    """Create a new venue for an organization (starts as draft)."""
    if current_user.org_id != orgId:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized"
        )
    return crud_venue.venue.create_with_organization(db, obj_in=venue_in, org_id=orgId)


@router.get("/organizations/{orgId}/venues", response_model=List[Venue])
def list_venues(
    orgId: str,
    status_filter: Optional[str] = Query(default=None, alias="status"),
    db: Session = Depends(get_db),
    current_user: TokenPayload = Depends(deps.get_current_user),
):
    """List all venues for an organization (including drafts, rejected, etc.)."""
    if current_user.org_id != orgId:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized"
        )
    return crud_venue.venue.get_multi_by_organization(
        db, org_id=orgId, status=status_filter
    )


@router.get("/organizations/{orgId}/venues/{venueId}", response_model=Venue)
def get_venue(
    orgId: str,
    venueId: str,
    db: Session = Depends(get_db),
    current_user: TokenPayload = Depends(deps.get_current_user),
):
    """Get full details of an org's venue (owner view)."""
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
    """Update venue details. Only non-null fields are applied."""
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
    """Archive (soft-delete) a venue."""
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


@router.post(
    "/organizations/{orgId}/venues/{venueId}/submit",
    response_model=VenueSubmitResponse,
)
def submit_venue_for_review(
    orgId: str,
    venueId: str,
    db: Session = Depends(get_db),
    current_user: TokenPayload = Depends(deps.get_current_user),
):
    """Submit venue for review. Transitions status from draft/rejected to pending_review."""
    if current_user.org_id != orgId:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized"
        )

    venue = crud_venue.venue.get(db, id=venueId)
    if not venue or venue.organization_id != orgId:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Venue not found"
        )

    if venue.status not in ("draft", "rejected"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Cannot submit venue with status '{venue.status}'. Must be 'draft' or 'rejected'.",
        )

    updated = crud_venue.venue.submit_for_review(db, venue_id=venueId)
    return VenueSubmitResponse(
        id=updated.id,
        status=updated.status,
        submitted_at=updated.submitted_at,
    )
