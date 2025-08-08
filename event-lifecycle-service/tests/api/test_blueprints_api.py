from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from app.crud import crud_blueprint
from app.schemas.blueprint import BlueprintCreate


def test_create_blueprint_api(client: TestClient):
    """
    Tests creating a new event blueprint.
    """
    blueprint_data = {
        "name": "Annual Sales Kick-off",
        "description": "Template for our yearly sales event.",
        "template": {"is_public": True, "status": "published"},
    }
    response = client.post(
        "/api/v1/organizations/acme-corp/blueprints", json=blueprint_data
    )
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Annual Sales Kick-off"
    assert data["template"]["is_public"] is True


def test_list_blueprints_api(client: TestClient, db_session: Session):
    """
    Tests listing all blueprints for an organization.
    """
    crud_blueprint.blueprint.create_with_organization(
        db_session,
        obj_in=BlueprintCreate(name="Blueprint 1", template={}),
        org_id="acme-corp",
    )
    crud_blueprint.blueprint.create_with_organization(
        db_session,
        obj_in=BlueprintCreate(name="Blueprint 2", template={}),
        org_id="other-corp",
    )
    response = client.get("/api/v1/organizations/acme-corp/blueprints")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["name"] == "Blueprint 1"
