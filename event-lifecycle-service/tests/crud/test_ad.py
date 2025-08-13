from unittest.mock import MagicMock
from app.crud.crud_ad import CRUDAd
from app.models.ad import Ad
from app.schemas.ad import AdCreate

# Instantiate the class to test its methods
ad_crud = CRUDAd(Ad)


def test_create_ad():
    """
    Tests the inherited create_with_organization method for Ads.
    """
    db_session = MagicMock()
    ad_in = AdCreate(
        name="Test Ad",
        content_type="BANNER",
        media_url="http://example.com/img.png",
        click_url="http://example.com",
    )

    ad_crud.create_with_organization(db=db_session, obj_in=ad_in, org_id="org_abc")

    db_session.add.assert_called_once()
    db_session.commit.assert_called_once()
    db_session.refresh.assert_called_once()
