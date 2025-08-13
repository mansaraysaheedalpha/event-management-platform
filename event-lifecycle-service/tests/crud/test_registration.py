# tests/crud/test_registration.py

from unittest.mock import MagicMock
from app.crud.crud_registration import CRUDRegistration
from app.models.registration import Registration
from app.schemas.registration import RegistrationCreate

registration_crud = CRUDRegistration(Registration)


def test_create_for_event_for_registered_user():
    """
    Tests creating a registration for a known user_id.
    """
    db_session = MagicMock()
    # Simulate that the generated ticket code is unique
    db_session.query.return_value.filter.return_value.first.return_value = None

    # Input has a user_id
    reg_in = RegistrationCreate(user_id="user_123")

    registration_crud.create_for_event(db=db_session, obj_in=reg_in, event_id="evt_1")

    # Check that the object passed to db.add has the correct user_id
    # and does not have guest details.
    created_obj = db_session.add.call_args[0][0]
    assert created_obj.user_id == "user_123"
    assert created_obj.guest_email is None


def test_create_for_event_for_guest_user():
    """
    Tests creating a registration for a guest.
    """
    db_session = MagicMock()
    db_session.query.return_value.filter.return_value.first.return_value = None

    # Input has guest details, but no user_id
    reg_in = RegistrationCreate(
        first_name="Guest", last_name="User", email="guest@example.com"
    )

    registration_crud.create_for_event(db=db_session, obj_in=reg_in, event_id="evt_1")

    created_obj = db_session.add.call_args[0][0]
    assert created_obj.user_id is None
    assert created_obj.guest_email == "guest@example.com"
    assert created_obj.guest_name == "Guest User"
