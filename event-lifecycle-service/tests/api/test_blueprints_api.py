from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from datetime import datetime, timedelta

from tests.utils.blueprint import create_random_blueprint
from tests.utils.auth import get_user_authentication_headers


def test_create_blueprint(client: TestClient, db: Session) -> None:
    """
    Tests creating a new event blueprint.
    """
    headers = get_user_authentication_headers(db, org_id="org_bp_test")
    data = {
        "name": "Annual Conference Blueprint",
        "template": {
            "description": "Default description from template",
            "is_public": False,
        },
    }

    response = client.post(
        "/api/v1/organizations/org_bp_test/blueprints", headers=headers, json=data
    )

    assert response.status_code == 201
    content = response.json()
    assert content["name"] == data["name"]
    assert content["template"]["is_public"] is False


# ... other standard CRUD tests for list, get, update, delete would follow the same pattern ...


def test_instantiate_blueprint(client: TestClient, db: Session) -> None:
    """
    Tests creating a new Event from a blueprint.
    """
    headers = get_user_authentication_headers(db, org_id="org_bp_test")
    # 1. First, create a blueprint to instantiate from
    blueprint = create_random_blueprint(
        db,
        org_id="org_bp_test",
        template={"description": "Instantiated Event", "is_public": True},
    )

    # 2. Define the new event's unique details
    start_date = datetime.utcnow() + timedelta(days=30)
    end_date = start_date + timedelta(days=2)
    instantiate_data = {
        "name": "My New Event From Blueprint",
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
    }

    # 3. Call the instantiate endpoint
    response = client.post(
        f"/api/v1/organizations/org_bp_test/blueprints/{blueprint.id}/instantiate",
        headers=headers,
        json=instantiate_data,
    )

    # 4. Assert that a valid Event was created
    assert response.status_code == 201
    event = response.json()

    # Check that the new details were applied
    assert event["name"] == instantiate_data["name"]

    # Check that the details from the blueprint template were also applied
    assert event["description"] == "Instantiated Event"
    assert event["is_public"] is True
    assert "id" in event
    assert event["status"] == "draft"  # Events are created as drafts by default
