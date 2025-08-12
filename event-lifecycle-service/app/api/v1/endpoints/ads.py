#app/api/v1/endpoints/ads.py
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api import deps
from app.db.session import get_db
from app.crud import crud_ad
from app.schemas.ad import Ad, AdCreate, AdUpdate
from app.schemas.token import TokenPayload

router = APIRouter(tags=["Ads"])


@router.post(
    "/organizations/{orgId}/ads", response_model=Ad, status_code=status.HTTP_201_CREATED
)
def create_ad(
    orgId: str,
    ad_in: AdCreate,
    db: Session = Depends(get_db),
    current_user: TokenPayload = Depends(deps.get_current_user),
):
    """
    Create a new ad for an organization.
    """
    if current_user.org_id != orgId:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized"
        )
    return crud_ad.ad.create_with_organization(db, obj_in=ad_in, org_id=orgId)


@router.get("/organizations/{orgId}/ads", response_model=List[Ad])
def list_ads(
    orgId: str,
    db: Session = Depends(get_db),
    current_user: TokenPayload = Depends(deps.get_current_user),
):
    """
    List all ads for an organization.
    """
    if current_user.org_id != orgId:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized"
        )
    return crud_ad.ad.get_multi_by_organization(db, org_id=orgId)
