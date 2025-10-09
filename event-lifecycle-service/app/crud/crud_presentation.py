# app/crud/crud_presentation.py
from sqlalchemy.orm import Session
from typing import List
from .base import CRUDBase
from app.models.presentation import Presentation
from app.schemas.presentation import Presentation as PresentationSchema


# Note: Presentation doesn't have a standard Create/Update schema
# because it's created based on file processing results.
class CRUDPresentation(CRUDBase[Presentation, PresentationSchema, PresentationSchema]):
    def get_by_session(self, db: Session, *, session_id: str) -> Presentation | None:
        return db.query(self.model).filter(self.model.session_id == session_id).first()

    def create_with_session(
        self, db: Session, *, session_id: str, slide_urls: List[str], status: str
    ) -> Presentation:
        # Check if one already exists to avoid unique constraint errors
        existing = self.get_by_session(db, session_id=session_id)
        if existing:
            # If we're retrying a failed upload, just update the existing one
            existing.status = status
            existing.slide_urls = slide_urls
            db.add(existing)
            db.commit()
            db.refresh(existing)
            return existing

        db_obj = self.model(session_id=session_id, slide_urls=slide_urls, status=status)
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj


presentation = CRUDPresentation(Presentation)
