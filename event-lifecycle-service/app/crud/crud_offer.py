from .base import CRUDBase
from app.models.offer import Offer
from app.schemas.offer import OfferCreate, OfferUpdate


class CRUDOffer(CRUDBase[Offer, OfferCreate, OfferUpdate]):
    pass


offer = CRUDOffer(Offer)
