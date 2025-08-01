from .base import CRUDBase
from app.models.ad import Ad
from app.schemas.ad import AdCreate, AdUpdate


class CRUDAd(CRUDBase[Ad, AdCreate, AdUpdate]):
    pass


ad = CRUDAd(Ad)
