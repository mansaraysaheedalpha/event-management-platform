from sqlalchemy.orm import Session
from app.crud import crud_event, crud_speaker, crud_session
from app.schemas.event import EventCreate
from app.schemas.speaker import SpeakerCreate
from app.schemas.session import SessionCreate
from datetime import datetime, timezone


def test_create_session_with_speakers(db_session: Session):
    """
    Tests the direct CRUD function for creating a session and linking speakers.
    """
    # ARRANGE: Create an event and speakers
    test_event = crud_event.event.create_with_organization(
        db_session,
        obj_in=EventCreate(
            name="Event for CRUD Test",
            start_date=datetime.now(timezone.utc),
            end_date=datetime.now(timezone.utc),
        ),
        org_id="acme-corp",
    )
    speaker1 = crud_speaker.speaker.create_with_organization(
        db_session, obj_in=SpeakerCreate(name="CRUD Speaker 1"), org_id="acme-corp"
    )
    speaker2 = crud_speaker.speaker.create_with_organization(
        db_session, obj_in=SpeakerCreate(name="CRUD Speaker 2"), org_id="acme-corp"
    )

    session_in = SessionCreate(
        title="CRUD Test Session",
        start_time=datetime.now(timezone.utc),
        end_time=datetime.now(timezone.utc),
        speaker_ids=[speaker1.id, speaker2.id],
    )

    # ACT: Call the CRUD function directly
    created_session = crud_session.session.create_with_event(
        db_session, obj_in=session_in, event_id=test_event.id
    )

    # ASSERT
    assert created_session is not None
    assert created_session.title == "CRUD Test Session"
    assert created_session.event_id == test_event.id
    assert len(created_session.speakers) == 2
    # Check that the actual speaker objects are linked
    assert created_session.speakers[0].name == "CRUD Speaker 1"
