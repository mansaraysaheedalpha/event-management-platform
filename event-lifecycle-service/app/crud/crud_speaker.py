from sqlalchemy.orm import Session
from typing import List
from datetime import datetime
from .base import CRUDBase
from app.models.speaker import Speaker
from app.schemas.speaker import SpeakerCreate, SpeakerUpdate
from app.models.session_speaker import session_speaker_association


class CRUDSpeaker(CRUDBase[Speaker, SpeakerCreate, SpeakerUpdate]):
    # You can add speaker-specific CRUD methods here if needed
    def get_available(
        self,
        db: Session,
        *,
        org_id: str,
        start_time: datetime,
        end_time: datetime,
        expertise: str | None = None
    ) -> List[Speaker]:
        """
        Finds speakers who do not have any sessions that overlap with the
        provided start_time and end_time.
        """
        # This is the correct logic for finding conflicting time ranges.
        # It finds any session where:
        # (Session starts before our window ends) AND (Session ends after our window starts)
        conflicting_session_subquery = (
            db.query(Session.id)
            .filter(Session.start_time < end_time, Session.end_time > start_time)
            .subquery()
        )

        # Get the IDs of speakers who are booked in those conflicting sessions
        booked_speaker_ids_subquery = (
            db.query(session_speaker_association.c.speaker_id)
            .filter(
                session_speaker_association.c.session_id.in_(
                    conflicting_session_subquery
                )
            )
            .subquery()
        )

        # Main query to find speakers
        query = db.query(Speaker).filter(Speaker.organization_id == org_id)

        # Filter by expertise if provided
        if expertise:
            query = query.filter(Speaker.expertise.any(expertise))

        # The final step: find all speakers whose ID is NOT IN the list of booked speakers
        query = query.filter(Speaker.id.notin_(booked_speaker_ids_subquery))

        return query.all()


speaker = CRUDSpeaker(Speaker)
