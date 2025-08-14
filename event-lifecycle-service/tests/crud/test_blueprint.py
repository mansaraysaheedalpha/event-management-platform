# tests/crud/test_blueprint.py
#Blueprint integration test
from unittest.mock import MagicMock
from app.crud.crud_blueprint import CRUDBlueprint
from app.models.blueprint import EventBlueprint
from app.schemas.blueprint import BlueprintCreate

blueprint_crud = CRUDBlueprint(EventBlueprint)


def test_create_blueprint():
    db_session = MagicMock()
    blueprint_in = BlueprintCreate(
        name="Test Blueprint", template={"description": "Default Description"}
    )

    blueprint_crud.create_with_organization(
        db=db_session, obj_in=blueprint_in, org_id="org_abc"
    )

    # Assert that the database session was used to add, commit, and refresh
    db_session.add.assert_called_once()
    db_session.commit.assert_called_once()
    db_session.refresh.assert_called_once()

    # Check that the created object has the correct attributes
    created_obj = db_session.add.call_args[0][0]
    assert created_obj.name == "Test Blueprint"
    assert created_obj.organization_id == "org_abc"
