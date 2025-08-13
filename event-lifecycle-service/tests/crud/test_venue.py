# tests/crud/test_venue.py

from unittest.mock import MagicMock
from app.crud.crud_venue import CRUDVenue
from app.models.venue import Venue
from app.schemas.venue import VenueCreate

# Instantiate the class to test its methods
venue_crud = CRUDVenue(Venue)


def test_create_venue():
    """
    Tests the inherited create_with_organization method.
    """
    db_session = MagicMock()
    venue_in = VenueCreate(name="Main Hall", address="123 Event St")

    venue_crud.create_with_organization(
        db=db_session, obj_in=venue_in, org_id="org_abc"
    )

    # Assert that the database session was used to add, commit, and refresh
    db_session.add.assert_called_once()
    db_session.commit.assert_called_once()
    db_session.refresh.assert_called_once()
