from typing import List, Optional
from sqlalchemy.orm import Session
from .base import CRUDBase
from app.models.session import Session
from app.models.speaker import Speaker
from app.schemas.session import SessionCreate, SessionUpdate


class CRUDSession(CRUDBase[Session, SessionCreate, SessionUpdate]):
    def get(self, db: Session, *, event_id: str, session_id: str) -> Optional[Session]:
        return (
            db.query(self.model)
            .filter(self.model.id == session_id, self.model.event_id == event_id)
            .first()
        )

    def get_multi_by_event(
        self, db: Session, *, event_id: str, skip: int = 0, limit: int = 100
    ) -> List[Session]:
        return (
            db.query(self.model)
            .filter(self.model.event_id == event_id, self.model.is_archived == False)
            .offset(skip)
            .limit(limit)
            .all()
        )

    def create_with_event(
        self, db: Session, *, obj_in: SessionCreate, event_id: str
    ) -> Session:
        speakers = []
        if obj_in.speaker_ids:
            speakers = (
                db.query(Speaker).filter(Speaker.id.in_(obj_in.speaker_ids)).all()
            )

        obj_in_data = obj_in.model_dump(exclude={"speaker_ids"})

        db_obj = self.model(**obj_in_data, event_id=event_id, speakers=speakers)
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def update(self, db: Session, *, db_obj: Session, obj_in: SessionUpdate) -> Session:
        # First, update the simple fields (title, start_time, etc.)
        # by calling the base update method.
        update_data = obj_in.model_dump(exclude_unset=True, exclude={"speaker_ids"})
        db_obj = super().update(db, db_obj=db_obj, obj_in=update_data)

        # Now, handle the speaker relationship if speaker_ids are provided
        if obj_in.speaker_ids is not None:
            speakers = (
                db.query(Speaker).filter(Speaker.id.in_(obj_in.speaker_ids)).all()
            )
            db_obj.speakers = speakers
            db.commit()
            db.refresh(db_obj)

        return db_obj


session = CRUDSession(Session)
