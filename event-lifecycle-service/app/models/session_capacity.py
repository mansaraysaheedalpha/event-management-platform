# app/models/session_capacity.py
from sqlalchemy import Column, String, ForeignKey, DateTime, Integer, func, CheckConstraint
from app.db.base_class import Base


class SessionCapacity(Base):
    """
    Session Capacity model for managing dynamic session attendance limits.

    Features:
    - Per-session maximum capacity configuration
    - Current attendance tracking
    - Automatic validation (attendance <= capacity)
    """
    __tablename__ = "session_capacity"

    session_id = Column(String, ForeignKey("sessions.id", ondelete="CASCADE"), primary_key=True, index=True)
    maximum_capacity = Column(Integer, nullable=False, server_default="100")
    current_attendance = Column(Integer, nullable=False, server_default="0")
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        CheckConstraint('maximum_capacity >= 0', name='check_capacity_positive'),
        CheckConstraint('current_attendance >= 0', name='check_attendance_positive'),
        CheckConstraint('current_attendance <= maximum_capacity', name='check_attendance_lte_capacity'),
    )
