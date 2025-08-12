# app/crud/crud_session.py
from typing import List, Optional
from sqlalchemy.orm import Session
from .base import CRUDBase
from app.models.session import Session
from app.models.speaker import Speaker
from app.schemas.session import SessionCreate, SessionUpdate
import json
from app.db.redis import redis_client
from datetime import datetime, timezone
from app.core.kafka_producer import producer


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

         # --- NEW: Inter-Service Communication to Oracle ---
        # Publish an attendance update message to Kafka for the Oracle to consume
        attendance_payload = {
            "eventId": event_id,
            "sessionId": db_obj.id,
            "currentAttendance": 0, # Starts at 0
            "capacity": 100, # Assuming a default capacity
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        producer.send("real-time.attendance.data", value=attendance_payload)
    
        return db_obj

    def update(self, db: Session, *, db_obj: Session, obj_in: SessionUpdate) -> Session:
        # --- 1. First, update the simple fields ---
        # (e.g., title, start_time) by calling the base update method.
        update_data = obj_in.model_dump(exclude_unset=True, exclude={"speaker_ids"})
        # The super().update handles the commit and refresh for these simple fields
        updated_session = super().update(db, db_obj=db_obj, obj_in=update_data)

        # --- 2. Now, handle the speaker relationship, if provided ---
        if obj_in.speaker_ids is not None:
            speakers = db.query(Speaker).filter(Speaker.id.in_(obj_in.speaker_ids)).all()
            updated_session.speakers = speakers
            db.add(updated_session)
            db.commit()
            db.refresh(updated_session)

        # --- 3. Finally, publish the notification with the fully updated data ---
        notification_payload = {
            "event_id": updated_session.event_id,
            "update_type": "SESSION_UPDATED",
            "session_data": {
                "id": updated_session.id,
                "event_id": updated_session.event_id,
                "title": updated_session.title,
                "start_time": updated_session.start_time.isoformat(),
                "end_time": updated_session.end_time.isoformat(),
                # Convert speaker objects to dictionaries for the JSON payload
                "speakers": [
                    {"id": s.id, "name": s.name, "bio": s.bio, "expertise": s.expertise} 
                    for s in updated_session.speakers
                ]
            }
        }
        redis_client.publish("platform.events.agenda.v1", json.dumps(notification_payload))

        return updated_session


session = CRUDSession(Session)
