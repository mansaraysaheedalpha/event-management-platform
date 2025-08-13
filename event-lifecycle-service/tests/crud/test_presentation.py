# tests/crud/test_presentation.py

from unittest.mock import MagicMock
from app.crud.crud_presentation import CRUDPresentation
from app.models.presentation import Presentation

presentation_crud = CRUDPresentation(Presentation)


def test_create_with_session():
    """
    Tests creating a presentation with a list of slide URLs.
    """
    db_session = MagicMock()

    session_id = "session_1"
    slide_urls = ["/path/to/slide1.jpg", "/path/to/slide2.jpg"]

    presentation_crud.create_with_session(
        db=db_session, session_id=session_id, slide_urls=slide_urls
    )

    # Get the object that was passed to db.add()
    created_obj = db_session.add.call_args[0][0]

    # Assert that the object has the correct properties
    assert created_obj.session_id == session_id
    assert created_obj.slide_urls == slide_urls

    # Assert that the database session was used to save the object
    db_session.add.assert_called_once()
    db_session.commit.assert_called_once()
