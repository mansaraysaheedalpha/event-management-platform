# app/db/models.py
from sqlalchemy import Column, Integer, String, JSON
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class KnowledgeBaseItem(Base):
    __tablename__ = "knowledge_base"
    id = Column(Integer, primary_key=True, index=True)
    category = Column(String, index=True)  # e.g., "competitors", "Germany"
    key = Column(String, index=True)  # e.g., "EventCorp", "Tech"
    data = Column(JSON)  # The actual intelligence data
