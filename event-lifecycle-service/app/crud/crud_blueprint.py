# app/crud/blueprint.py
from .base import CRUDBase
from app.models.blueprint import EventBlueprint
from app.schemas.blueprint import BlueprintCreate, BlueprintUpdate


class CRUDBlueprint(CRUDBase[EventBlueprint, BlueprintCreate, BlueprintUpdate]):
    pass


blueprint = CRUDBlueprint(EventBlueprint)
