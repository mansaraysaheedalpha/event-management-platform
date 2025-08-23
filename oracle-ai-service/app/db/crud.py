# app/db/crud.py
from sqlalchemy.orm import Session
from . import models


def get_kb_entry(db: Session, category: str, key: str) -> dict:
    entry = (
        db.query(models.KnowledgeBaseItem)
        .filter(
            models.KnowledgeBaseItem.category == category,
            models.KnowledgeBaseItem.key == key,
        )
        .first()
    )
    return entry.data if entry else {}


def get_kb_category(db: Session, category: str) -> list:
    entries = (
        db.query(models.KnowledgeBaseItem)
        .filter(models.KnowledgeBaseItem.category == category)
        .all()
    )
    return [{item.key: item.data} for item in entries]
