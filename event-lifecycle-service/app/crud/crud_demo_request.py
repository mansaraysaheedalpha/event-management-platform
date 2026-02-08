# app/crud/crud_demo_request.py
from typing import List, Optional
from sqlalchemy.orm import Session

from app.models.demo_request import DemoRequest
from app.schemas.demo_request import DemoRequestCreate


class CRUDDemoRequest:
    def __init__(self, model):
        self.model = model

    def create(self, db: Session, *, obj_in: DemoRequestCreate) -> DemoRequest:
        obj_in_data = obj_in.model_dump()
        db_obj = self.model(**obj_in_data)
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def get(self, db: Session, *, id: str) -> Optional[DemoRequest]:
        return db.query(self.model).filter(self.model.id == id).first()

    def get_multi(
        self, db: Session, *, skip: int = 0, limit: int = 100
    ) -> List[DemoRequest]:
        return db.query(self.model).order_by(
            self.model.created_at.desc()
        ).offset(skip).limit(limit).all()


demo_request = CRUDDemoRequest(DemoRequest)
