from unittest.mock import MagicMock
from app.crud.crud_offer import CRUDOffer
from app.models.offer import Offer
from app.schemas.offer import OfferCreate

# Instantiate the class to test its methods
offer_crud = CRUDOffer(Offer)


def test_create_offer():
    """
    Tests the inherited create_with_organization method for Offers.
    """
    db_session = MagicMock()
    offer_in = OfferCreate(
        event_id="evt_1", title="VIP Upgrade", price=99.99, offer_type="TICKET_UPGRADE"
    )

    offer_crud.create_with_organization(
        db=db_session, obj_in=offer_in, org_id="org_abc"
    )

    db_session.add.assert_called_once()
    db_session.commit.assert_called_once()
    db_session.refresh.assert_called_once()
