# app/crud/crud_venue_verification.py
from typing import Optional, List
from sqlalchemy.orm import Session

from app.models.venue_verification_document import VenueVerificationDocument
from app.core.config import settings
from app.core.s3 import generate_presigned_download_url


class CRUDVenueVerification:
    def create(self, db: Session, *, venue_id: str, obj_in: dict) -> VenueVerificationDocument:
        # H-17: Don't store public URLs — generate presigned GET on demand
        db_obj = VenueVerificationDocument(
            venue_id=venue_id,
            document_type=obj_in["document_type"],
            url="",  # populated on-demand via presigned URL
            s3_key=obj_in["s3_key"],
            filename=obj_in["filename"],
        )
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def get(self, db: Session, *, id: str) -> Optional[VenueVerificationDocument]:
        return (
            db.query(VenueVerificationDocument)
            .filter(VenueVerificationDocument.id == id)
            .first()
        )

    def get_multi_by_venue(
        self, db: Session, *, venue_id: str
    ) -> List[VenueVerificationDocument]:
        return (
            db.query(VenueVerificationDocument)
            .filter(VenueVerificationDocument.venue_id == venue_id)
            .order_by(VenueVerificationDocument.created_at.desc())
            .all()
        )

    def get_multi_by_venue_with_urls(
        self, db: Session, *, venue_id: str
    ) -> List[dict]:
        """Return verification docs with presigned download URLs."""
        docs = self.get_multi_by_venue(db, venue_id=venue_id)
        result = []
        for doc in docs:
            result.append({
                "id": doc.id,
                "venue_id": doc.venue_id,
                "document_type": doc.document_type,
                "url": generate_presigned_download_url(doc.s3_key, doc.filename),
                "s3_key": doc.s3_key,
                "filename": doc.filename,
                "status": doc.status,
                "admin_notes": doc.admin_notes,
                "created_at": doc.created_at,
                "updated_at": doc.updated_at,
            })
        return result

    def update_status(
        self, db: Session, *, id: str, status: str, admin_notes: str = None
    ) -> Optional[VenueVerificationDocument]:
        """H-06: Update verification document status."""
        doc = self.get(db, id=id)
        if not doc:
            return None
        doc.status = status
        if admin_notes is not None:
            doc.admin_notes = admin_notes
        db.add(doc)
        db.commit()
        db.refresh(doc)
        return doc


venue_verification = CRUDVenueVerification()
