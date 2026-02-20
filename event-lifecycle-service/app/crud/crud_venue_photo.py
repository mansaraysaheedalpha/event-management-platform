# app/crud/crud_venue_photo.py
from typing import Optional, List
from sqlalchemy.orm import Session
import logging

from app.models.venue_photo import VenuePhoto
from app.core.config import settings

logger = logging.getLogger(__name__)


class CRUDVenuePhoto:
    def create(self, db: Session, *, venue_id: str, obj_in: dict) -> VenuePhoto:
        # Build public URL from s3_key
        bucket = settings.AWS_S3_BUCKET_NAME
        region = settings.AWS_S3_REGION
        url = f"https://{bucket}.s3.{region}.amazonaws.com/{obj_in['s3_key']}"

        db_obj = VenuePhoto(
            venue_id=venue_id,
            url=url,
            s3_key=obj_in["s3_key"],
            category=obj_in.get("category"),
            caption=obj_in.get("caption"),
            is_cover=obj_in.get("is_cover", False),
            space_id=obj_in.get("space_id"),
        )

        # If this is set as cover, unset any existing cover
        if db_obj.is_cover:
            self._unset_cover(db, venue_id=venue_id)

        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def get(self, db: Session, *, id: str) -> Optional[VenuePhoto]:
        return db.query(VenuePhoto).filter(VenuePhoto.id == id).first()

    def get_multi_by_venue(self, db: Session, *, venue_id: str) -> List[VenuePhoto]:
        return (
            db.query(VenuePhoto)
            .filter(VenuePhoto.venue_id == venue_id)
            .order_by(VenuePhoto.sort_order)
            .all()
        )

    def count_by_venue(self, db: Session, *, venue_id: str) -> int:
        return db.query(VenuePhoto).filter(VenuePhoto.venue_id == venue_id).count()

    def update(self, db: Session, *, db_obj: VenuePhoto, obj_in: dict) -> VenuePhoto:
        # Handle cover toggle
        if obj_in.get("is_cover") is True:
            self._unset_cover(db, venue_id=db_obj.venue_id)

        for field, value in obj_in.items():
            if value is not None:
                setattr(db_obj, field, value)
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def delete(self, db: Session, *, id: str) -> Optional[str]:
        """Delete photo and return s3_key for cleanup."""
        obj = db.query(VenuePhoto).filter(VenuePhoto.id == id).first()
        if not obj:
            return None
        s3_key = obj.s3_key
        db.delete(obj)
        db.commit()
        return s3_key

    def reorder(self, db: Session, *, venue_id: str, photo_ids: List[str]) -> List[VenuePhoto]:
        photos = (
            db.query(VenuePhoto)
            .filter(VenuePhoto.venue_id == venue_id)
            .all()
        )
        photo_map = {p.id: p for p in photos}

        for idx, photo_id in enumerate(photo_ids):
            if photo_id in photo_map:
                photo_map[photo_id].sort_order = idx

        db.commit()
        return (
            db.query(VenuePhoto)
            .filter(VenuePhoto.venue_id == venue_id)
            .order_by(VenuePhoto.sort_order)
            .all()
        )

    def _unset_cover(self, db: Session, *, venue_id: str):
        db.query(VenuePhoto).filter(
            VenuePhoto.venue_id == venue_id,
            VenuePhoto.is_cover == True,
        ).update({"is_cover": False})


venue_photo = CRUDVenuePhoto()
