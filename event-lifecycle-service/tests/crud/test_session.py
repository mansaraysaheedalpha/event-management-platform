# tests/crud/test_session.py

from unittest.mock import MagicMock, patch, ANY
from app.crud.crud_session import CRUDSession
from app.models.session import Session
from app.models.speaker import Speaker
from app.schemas.session import SessionCreate, SessionUpdate
from datetime import datetime, timezone

session_crud = CRUDSession(Session)


def test_update_session_speakers_and_title():
    db_session = MagicMock()

    # **FIX**: Create a more complete mock object with all necessary fields
    db_obj = Session(
        id="session_1",
        title="Old Title",
        speakers=[],
        event_id="evt_1",
        start_time=datetime.now(timezone.utc),
        end_time=datetime.now(timezone.utc),
    )
    new_speakers = [Speaker(id="spk_3")]
    db_session.query.return_value.filter.return_value.all.return_value = new_speakers

    session_in = SessionUpdate(title="New Title", speaker_ids=["spk_3"])

    with patch("app.crud.base.CRUDBase.update") as mock_super_update, patch(
        "app.crud.crud_session.redis_client"
    ) as mock_redis_client:

        def simulate_super_update(db, db_obj, obj_in):
            db_obj.title = obj_in.get("title", db_obj.title)
            return db_obj

        mock_super_update.side_effect = simulate_super_update

        updated_session = session_crud.update(
            db=db_session, db_obj=db_obj, obj_in=session_in
        )

        assert updated_session.title == "New Title"
        assert len(updated_session.speakers) == 1
        assert updated_session.speakers[0].id == "spk_3"
        mock_super_update.assert_called_once_with(
            db=db_session, db_obj=db_obj, obj_in={"title": "New Title"}
        )
        mock_redis_client.publish.assert_called_once()
