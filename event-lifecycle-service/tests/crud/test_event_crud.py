from datetime import datetime, timedelta, timezone
from app.crud import crud_event
from app.schemas.event import EventCreate


def test_create_event(db_session):
    """
    Tests the creation of an event in the database.
    """
    # ARRANGE
    event_in = EventCreate(
        name="Test Event",
        start_date=datetime.now(timezone.utc),
        end_date=datetime.now(timezone.utc) + timedelta(days=1),
    )
    org_id = "test_org_123"

    # ACT
    created_event = crud_event.event.create_with_organization(
        db=db_session, obj_in=event_in, org_id=org_id
    )

    # ASSERT
    assert created_event is not None
    assert created_event.id is not None
    assert created_event.name == "Test Event"
    assert created_event.organization_id == org_id
    assert created_event.status == "draft"  # Check default value
