# app/models/session_speaker.py
from sqlalchemy import Table, Column, String, ForeignKey
from app.db.base_class import Base

# This is our association table. It doesn't have its own model class.
# It consists only of the foreign keys to the two tables it links.
session_speaker_association = Table(
    "session_speaker_association",
    Base.metadata,
    Column("session_id", String, ForeignKey("sessions.id"), primary_key=True),
    Column("speaker_id", String, ForeignKey("speakers.id"), primary_key=True),
)
