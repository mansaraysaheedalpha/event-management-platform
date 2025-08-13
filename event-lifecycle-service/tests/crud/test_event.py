from unittest.mock import MagicMock, patch
from app.crud.crud_event import CRUDEvent
from app.models.event import Event
from app.schemas.event import EventUpdate

event_crud = CRUDEvent(Event)


def test_update_logs_changes():
    """
    Tests that the custom update method correctly identifies changes
    and creates a domain event log.
    """
    db_session = MagicMock()

    db_obj = Event(id="evt_1", name="Old Name", status="draft")

    obj_in = EventUpdate(name="New Name")

    with patch("app.crud.base.CRUDBase.update") as mock_super_update, patch(
        "app.crud.crud_event.crud_domain_event"
    ) as mock_domain_event_crud:

        mock_super_update.return_value = db_obj

        event_crud.update(
            db=db_session, db_obj=db_obj, obj_in=obj_in, user_id="user_123"
        )

        mock_super_update.assert_called_once()
        mock_domain_event_crud.domain_event.create_log.assert_called_once()

        # **THE FIX**: Access keyword arguments ('kwargs') instead of positional arguments ('call_args')
        # to get the 'data' payload.
        change_data = mock_domain_event_crud.domain_event.create_log.call_args.kwargs[
            "data"
        ]

        assert change_data == {"name": {"old": "Old Name", "new": "New Name"}}


def test_publish_event():
    """
    Tests that publishing an event changes its status and creates a domain event log.
    """
    db_session = MagicMock()
    db_obj = Event(id="evt_1", name="Test Event", status="draft")

    with patch("app.crud.crud_event.crud_domain_event") as mock_domain_event_crud:
        updated_event = event_crud.publish(
            db=db_session, db_obj=db_obj, user_id="user_123"
        )

        assert updated_event.status == "published"
        db_session.add.assert_called_once_with(db_obj)
        db_session.commit.assert_called_once()
        mock_domain_event_crud.domain_event.create_log.assert_called_once()
