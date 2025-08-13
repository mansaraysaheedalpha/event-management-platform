# tests/api/v1/test_speakers.py

from fastapi.testclient import TestClient
from unittest.mock import MagicMock

from app.schemas.speaker import Speaker as SpeakerSchema

crud_speaker_mock = MagicMock()


class MockTokenPayload:
    def __init__(self, sub, org_id):
        self.sub = sub
        self.org_id = org_id


def override_get_current_user():
    return MockTokenPayload(sub="user_123", org_id="org_abc")


def test_create_speaker(monkeypatch, test_client: TestClient):
    monkeypatch.setattr("app.api.v1.endpoints.speakers.crud_speaker", crud_speaker_mock)

    speaker_data = {"name": "Dr. Ada Lovelace", "bio": "Pioneering computer scientist."}

    # **FIX**: Return a full Pydantic schema object
    return_speaker = SpeakerSchema(
        id="spk_1", organization_id="org_abc", is_archived=False, **speaker_data
    )
    crud_speaker_mock.speaker.create_with_organization.return_value = return_speaker

    response = test_client.post("/api/v1/organizations/org_abc/speakers", json=speaker_data)

    assert response.status_code == 201
    assert response.json()["name"] == "Dr. Ada Lovelace"


def test_list_speakers(monkeypatch, test_client: TestClient):
    monkeypatch.setattr("app.api.v1.endpoints.speakers.crud_speaker", crud_speaker_mock)

    crud_speaker_mock.speaker.get_multi_by_organization.return_value = [
        SpeakerSchema(
            id="spk_1", name="Speaker One", organization_id="org_abc", is_archived=False
        ),
        SpeakerSchema(
            id="spk_2", name="Speaker Two", organization_id="org_abc", is_archived=False
        ),
    ]

    response = test_client.get("/api/v1/organizations/org_abc/speakers")

    assert response.status_code == 200
    assert len(response.json()) == 2
