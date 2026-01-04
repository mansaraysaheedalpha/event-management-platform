# app/crud/crud_session_capacity.py
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.models.session_capacity import SessionCapacity


class CRUDSessionCapacity:
    """CRUD operations for Session Capacity management."""

    def get_by_session(self, db: Session, session_id: str) -> Optional[SessionCapacity]:
        """Get capacity settings for a specific session."""
        return db.query(SessionCapacity).filter(SessionCapacity.session_id == session_id).first()

    def get_or_create(self, db: Session, session_id: str, default_capacity: int = 100) -> SessionCapacity:
        """
        Get existing capacity or create with default values.
        Useful for backward compatibility with sessions that don't have capacity set yet.
        """
        capacity = self.get_by_session(db, session_id)
        if not capacity:
            capacity = SessionCapacity(
                session_id=session_id,
                maximum_capacity=default_capacity,
                current_attendance=0
            )
            db.add(capacity)
            db.commit()
            db.refresh(capacity)
        return capacity

    def create(
        self,
        db: Session,
        session_id: str,
        maximum_capacity: int = 100,
        current_attendance: int = 0
    ) -> SessionCapacity:
        """Create a new session capacity entry."""
        capacity = SessionCapacity(
            session_id=session_id,
            maximum_capacity=maximum_capacity,
            current_attendance=current_attendance
        )
        db.add(capacity)
        db.commit()
        db.refresh(capacity)
        return capacity

    def update_maximum_capacity(
        self,
        db: Session,
        session_id: str,
        new_capacity: int
    ) -> Optional[SessionCapacity]:
        """
        Update the maximum capacity for a session.
        Returns None if new capacity is less than current attendance.
        """
        capacity = self.get_or_create(db, session_id)

        # Validation: cannot set capacity below current attendance
        if new_capacity < capacity.current_attendance:
            return None

        capacity.maximum_capacity = new_capacity
        capacity.updated_at = func.now()
        db.commit()
        db.refresh(capacity)
        return capacity

    def increment_attendance(self, db: Session, session_id: str) -> Optional[SessionCapacity]:
        """
        Increment current attendance by 1.
        Returns None if session is at capacity.
        """
        capacity = self.get_or_create(db, session_id)

        # Check if session is full
        if capacity.current_attendance >= capacity.maximum_capacity:
            return None

        capacity.current_attendance += 1
        capacity.updated_at = func.now()
        db.commit()
        db.refresh(capacity)
        return capacity

    def decrement_attendance(self, db: Session, session_id: str) -> SessionCapacity:
        """Decrement current attendance by 1."""
        capacity = self.get_or_create(db, session_id)

        # Ensure attendance doesn't go below 0
        if capacity.current_attendance > 0:
            capacity.current_attendance -= 1
            capacity.updated_at = func.now()
            db.commit()
            db.refresh(capacity)

        return capacity

    def is_full(self, db: Session, session_id: str) -> bool:
        """Check if session has reached capacity."""
        capacity = self.get_or_create(db, session_id)
        return capacity.current_attendance >= capacity.maximum_capacity

    def available_spots(self, db: Session, session_id: str) -> int:
        """Calculate number of available spots."""
        capacity = self.get_or_create(db, session_id)
        return max(0, capacity.maximum_capacity - capacity.current_attendance)

    def delete(self, db: Session, session_id: str) -> bool:
        """Delete capacity settings for a session."""
        capacity = self.get_by_session(db, session_id)
        if capacity:
            db.delete(capacity)
            db.commit()
            return True
        return False


# Singleton instance
session_capacity_crud = CRUDSessionCapacity()
