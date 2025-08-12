#app/crud/crud_venue.py
from .base import CRUDBase
from app.models.venue import Venue
from app.schemas.venue import VenueCreate, VenueUpdate


class CRUDVenue(CRUDBase[Venue, VenueCreate, VenueUpdate]):
    pass


venue = CRUDVenue(Venue)
