from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api import deps
from app.db.session import get_db
from app.crud import crud_offer
from app.schemas.offer import Offer, OfferCreate, OfferUpdate
from app.schemas.token import TokenPayload

router = APIRouter(tags=["Offers"])


@router.post(
    "/organizations/{orgId}/offers",
    response_model=Offer,
    status_code=status.HTTP_201_CREATED,
)
def create_offer(
    orgId: str,
    offer_in: OfferCreate,
    db: Session = Depends(get_db),
    current_user: TokenPayload = Depends(deps.get_current_user),
):
    """
    Create a new offer for an organization.
    """
    if current_user.org_id != orgId:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized"
        )
    return crud_offer.offer.create_with_organization(db, obj_in=offer_in, org_id=orgId)


@router.get("/organizations/{orgId}/offers", response_model=List[Offer])
def list_offers(
    orgId: str,
    db: Session = Depends(get_db),
    current_user: TokenPayload = Depends(deps.get_current_user),
):
    """
    List all offers for an organization.
    """
    if current_user.org_id != orgId:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized"
        )
    return crud_offer.offer.get_multi_by_organization(db, org_id=orgId)
