from sqlalchemy.orm import Session
from app.crud import crud_ad
from app.schemas.ad import AdCreate
from app.models.ad import Ad


def create_random_ad(db: Session, org_id: str) -> Ad:
    """
    Creates a dummy ad for testing purposes.
    """
    ad_in = AdCreate(
        name="Test Ad Campaign",
        content_type="BANNER",
        media_url="https://example.com/test_ad.png",
        click_url="https://example.com/product_page",
    )
    return crud_ad.ad.create_with_organization(db, obj_in=ad_in, org_id=org_id)
