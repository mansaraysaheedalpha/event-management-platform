# app/crud/crud_presentation.py
from sqlalchemy.orm import Session
from typing import List, Optional
from .base import CRUDBase
from app.models.presentation import Presentation
from app.schemas.presentation import Presentation as PresentationSchema


# Note: Presentation doesn't have a standard Create/Update schema
# because it's created based on file processing results.
class CRUDPresentation(CRUDBase[Presentation, PresentationSchema, PresentationSchema]):
    def get_by_session(self, db: Session, *, session_id: str) -> Presentation | None:
        return db.query(self.model).filter(self.model.session_id == session_id).first()

    def create_with_session(
        self,
        db: Session,
        *,
        session_id: str,
        slide_urls: List[str],
        status: str,
        original_file_key: Optional[str] = None,
        original_filename: Optional[str] = None,
    ) -> Presentation:
        """
        Create or update a presentation for a session.

        Args:
            session_id: The session this presentation belongs to
            slide_urls: List of URLs for the processed slide images
            status: Processing status (processing, ready, failed)
            original_file_key: S3 key of the original uploaded file (for download)
            original_filename: Original filename of the uploaded file (for download)
        """
        # Check if one already exists to avoid unique constraint errors
        existing = self.get_by_session(db, session_id=session_id)
        if existing:
            # If we're retrying a failed upload, update the existing one
            existing.status = status
            existing.slide_urls = slide_urls
            if original_file_key is not None:
                existing.original_file_key = original_file_key
            if original_filename is not None:
                existing.original_filename = original_filename
            db.add(existing)
            db.commit()
            db.refresh(existing)
            return existing

        db_obj = self.model(
            session_id=session_id,
            slide_urls=slide_urls,
            status=status,
            original_file_key=original_file_key,
            original_filename=original_filename,
        )
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def toggle_download(
        self, db: Session, *, session_id: str, enabled: bool
    ) -> Presentation | None:
        """Toggle download availability for a presentation."""
        presentation = self.get_by_session(db, session_id=session_id)
        if presentation:
            presentation.download_enabled = enabled
            db.add(presentation)
            db.commit()
            db.refresh(presentation)
        return presentation


presentation = CRUDPresentation(Presentation)
