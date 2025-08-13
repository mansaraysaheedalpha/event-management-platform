from unittest.mock import MagicMock
from app.crud.crud_speaker import CRUDSpeaker, Speaker
from app.models.session import Session
from datetime import datetime, timezone

speaker_crud = CRUDSpeaker(Speaker)


def test_get_available_speakers():
    """
    Tests the logic for finding available speakers using an advanced mock.
    """
    mock_db_session = MagicMock()
    mock_query_result = [Speaker(id="spk_1", name="Available Speaker")]

    # --- Advanced Mock Setup ---
    mock_speaker_query_chain = MagicMock()
    mock_speaker_query_chain.filter.return_value.filter.return_value.all.return_value = (
        mock_query_result
    )

    mock_subquery_chain = MagicMock()
    # **THE FIX**: The subquery should return another MagicMock, not a string.
    # This mock object is a valid stand-in for the complex object SQLAlchemy expects.
    mock_subquery_chain.filter.return_value.subquery.return_value = MagicMock()

    mock_db_session.query.side_effect = [
        mock_subquery_chain,  # For the first db.query() call
        mock_subquery_chain,  # For the second call
        mock_speaker_query_chain,  # For the final call
    ]
    # --- End of Advanced Mock Setup ---

    speakers = speaker_crud.get_available(
        db=mock_db_session,
        org_id="org_1",
        start_time=datetime.now(timezone.utc),
        end_time=datetime.now(timezone.utc),
    )

    assert len(speakers) == 1
    assert speakers[0].name == "Available Speaker"
