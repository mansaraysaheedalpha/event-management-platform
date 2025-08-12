from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from app.crud import crud_speaker
from app.schemas.speaker import SpeakerCreate


def test_create_speaker_api(client: TestClient):
    """
    Tests the successful creation of a new speaker.
    """
    # ARRANGE
    speaker_data = {
        "name": "Dr. Evelyn Reed",
        "bio": "A leading expert in AI.",
        "expertise": ["AI", "Machine Learning"],
    }

    # ACT
    response = client.post(
        "/api/v1/organizations/acme-corp/speakers", json=speaker_data
    )

    # ASSERT
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Dr. Evelyn Reed"
    assert data["organization_id"] == "acme-corp"
    assert "id" in data


def test_list_speakers_api(client: TestClient, db_session: Session):
    """
    Tests listing all speakers for a specific organization.
    """
    # ARRANGE: Create a couple of speakers
    crud_speaker.speaker.create_with_organization(
        db_session, obj_in=SpeakerCreate(name="Speaker A"), org_id="acme-corp"
    )
    crud_speaker.speaker.create_with_organization(
        db_session, obj_in=SpeakerCreate(name="Speaker B"), org_id="other-corp"
    )

    # ACT
    response = client.get("/api/v1/organizations/acme-corp/speakers")

    # ASSERT
    assert response.status_code == 200
    data = response.json()
    # Should only return the one speaker from acme-corp
    assert len(data) == 1
    assert data[0]["name"] == "Speaker A"
