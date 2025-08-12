from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from app.crud import crud_event, crud_speaker, crud_session
from app.schemas.event import EventCreate
from app.schemas.speaker import SpeakerCreate
from app.schemas.session import SessionCreate
from datetime import datetime, timezone


def test_create_session_api(client: TestClient, db_session: Session):
    """
    Tests the successful creation of a new session for an event.
    """
    # ARRANGE: Create an event and two speakers to associate with the session
    test_event = crud_event.event.create_with_organization(
        db_session,
        obj_in=EventCreate(
            name="Test Event for Sessions",
            start_date=datetime.utcnow(),
            end_date=datetime.utcnow(),
        ),
        org_id="acme-corp",
    )
    speaker1 = crud_speaker.speaker.create_with_organization(
        db_session, obj_in=SpeakerCreate(name="Speaker One"), org_id="acme-corp"
    )
    speaker2 = crud_speaker.speaker.create_with_organization(
        db_session, obj_in=SpeakerCreate(name="Speaker Two"), org_id="acme-corp"
    )

    session_data = {
        "title": "My First Session",
        "start_time": "2025-11-10T10:00:00Z",
        "end_time": "2025-11-10T11:00:00Z",
        "speaker_ids": [speaker1.id, speaker2.id],
    }

    # ACT: Make the API request to create the session
    response = client.post(
        f"/api/v1/organizations/acme-corp/events/{test_event.id}/sessions",
        json=session_data,
    )

    # ASSERT
    assert response.status_code == 201
    data = response.json()
    assert data["title"] == "My First Session"
    assert data["event_id"] == test_event.id
    assert len(data["speakers"]) == 2
    assert data["speakers"][0]["name"] == "Speaker One"


def test_create_session_for_nonexistent_event(client: TestClient):
    """
    Tests that creating a session for a non-existent event fails with a 404 error.
    """
    # ARRANGE
    session_data = {
        "title": "My First Session",
        "start_time": "2025-11-10T10:00:00Z",
        "end_time": "2025-11-10T11:00:00Z",
        "speaker_ids": [],
    }
    non_existent_event_id = "evt_nonexistent"

    # ACT
    response = client.post(
        f"/api/v1/organizations/acme-corp/events/{non_existent_event_id}/sessions",
        json=session_data,
    )

    # ASSERT
    assert response.status_code == 404


def test_list_sessions_api(client: TestClient, db_session: Session):
    """
    Tests listing all sessions for a specific event.
    """
    test_event = crud_event.event.create_with_organization(
        db_session,
        obj_in=EventCreate(
            name="Test Event for Listing Sessions",
            start_date=datetime.now(timezone.utc),
            end_date=datetime.now(timezone.utc),
        ),
        org_id="acme-corp",
    )

    # FIX: Create Pydantic SessionCreate objects
    session_a_in = SessionCreate(
        title="Session A",
        start_time=datetime.now(timezone.utc),
        end_time=datetime.now(timezone.utc),
        speaker_ids=[],
    )
    session_b_in = SessionCreate(
        title="Session B",
        start_time=datetime.now(timezone.utc),
        end_time=datetime.now(timezone.utc),
        speaker_ids=[],
    )

    crud_session.session.create_with_event(
        db_session, obj_in=session_a_in, event_id=test_event.id
    )
    crud_session.session.create_with_event(
        db_session, obj_in=session_b_in, event_id=test_event.id
    )

    response = client.get(
        f"/api/v1/organizations/acme-corp/events/{test_event.id}/sessions"
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    assert data[0]["title"] == "Session A"


def test_update_session_api(client: TestClient, db_session: Session):
    """
    Tests updating a specific session.
    """
    test_event = crud_event.event.create_with_organization(
        db_session,
        obj_in=EventCreate(
            name="Event",
            start_date=datetime.now(timezone.utc),
            end_date=datetime.now(timezone.utc),
        ),
        org_id="acme-corp",
    )

    # FIX: Create a Pydantic SessionCreate object
    session_in = SessionCreate(
        title="Original Title",
        start_time=datetime.now(timezone.utc),
        end_time=datetime.now(timezone.utc),
    )
    test_session = crud_session.session.create_with_event(
        db_session, obj_in=session_in, event_id=test_event.id
    )

    update_data = {"title": "Updated Session Title"}

    response = client.patch(
        f"/api/v1/organizations/acme-corp/events/{test_event.id}/sessions/{test_session.id}",
        json=update_data,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "Updated Session Title"


def test_delete_session_api(client: TestClient, db_session: Session):
    """
    Tests deleting a specific session.
    """
    test_event = crud_event.event.create_with_organization(
        db_session,
        obj_in=EventCreate(
            name="Event",
            start_date=datetime.now(timezone.utc),
            end_date=datetime.now(timezone.utc),
        ),
        org_id="acme-corp",
    )

    # FIX: Create a Pydantic SessionCreate object
    session_in = SessionCreate(
        title="To Be Deleted",
        start_time=datetime.now(timezone.utc),
        end_time=datetime.now(timezone.utc),
    )
    test_session = crud_session.session.create_with_event(
        db_session, obj_in=session_in, event_id=test_event.id
    )

    response = client.delete(
        f"/api/v1/organizations/acme-corp/events/{test_event.id}/sessions/{test_session.id}"
    )

    assert response.status_code == 204

    deleted_session = crud_session.session.get(
        db_session, event_id=test_event.id, session_id=test_session.id
    )
    assert deleted_session.is_archived is True
