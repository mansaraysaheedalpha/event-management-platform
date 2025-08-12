from sqlalchemy.orm import Session
from app.crud import crud_blueprint
from app.schemas.blueprint import BlueprintCreate
from app.models.blueprint import EventBlueprint


def create_random_blueprint(
    db: Session, org_id: str, template: dict = None
) -> EventBlueprint:
    """
    Creates a dummy event blueprint for testing purposes.
    """
    if template is None:
        template = {"description": "Default blueprint template"}

    blueprint_in = BlueprintCreate(name="Test Blueprint", template=template)
    return crud_blueprint.blueprint.create_with_organization(
        db, obj_in=blueprint_in, org_id=org_id
    )
