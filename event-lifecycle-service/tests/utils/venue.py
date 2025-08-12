from sqlalchemy.orm import Session
from app.crud import crud_venue
from app.schemas.venue import VenueCreate
from app.models.venue import Venue


def create_random_venue(db: Session, org_id: str) -> Venue:
    """
    Creates a dummy venue for testing purposes.
    """
    venue_in = VenueCreate(name="Test Venue", address="123 Test Lane")
    return crud_venue.venue.create_with_organization(db, obj_in=venue_in, org_id=org_id)
