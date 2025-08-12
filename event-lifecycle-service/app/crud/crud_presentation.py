#app/crud/crud_presentation.py
from sqlalchemy.orm import Session
from typing import List
from .base import CRUDBase
from app.models.presentation import Presentation
from app.schemas.presentation import Presentation as PresentationSchema


# Note: Presentation doesn't have a standard Create/Update schema
# because it's created based on file processing results.
class CRUDPresentation(CRUDBase[Presentation, PresentationSchema, PresentationSchema]):
    def create_with_session(
        self, db: Session, *, session_id: str, slide_urls: List[str]
    ) -> Presentation:
        db_obj = self.model(session_id=session_id, slide_urls=slide_urls)
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj


presentation = CRUDPresentation(Presentation)
