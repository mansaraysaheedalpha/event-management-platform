# app/crud/crud_registration.py
import random
import string
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_
from .base import CRUDBase
from app.models.registration import Registration
from app.schemas.registration import RegistrationCreate, RegistrationUpdate


def generate_ticket_code(length: int = 8) -> str:
    """Generates a random alphanumeric ticket code."""
    # Example: A5D-G8K-9B1
    chars = string.ascii_uppercase + string.digits
    code = "".join(random.choice(chars) for _ in range(length))
    # Add dashes for readability
    return "-".join(code[i : i + 3] for i in range(0, len(code), 3))


class CRUDRegistration(CRUDBase[Registration, RegistrationCreate, RegistrationUpdate]):
    def get_by_user_or_email(
        self, db: Session, *, event_id: str, user_id: str = None, email: str = None
    ) -> Registration | None:
        """
        Checks if a registration exists for a user_id or guest email for a specific event.
        """
        if user_id:
            return (
                db.query(self.model)
                .filter(
                    and_(self.model.event_id == event_id, self.model.user_id == user_id)
                )
                .first()
            )
        if email:
            return (
                db.query(self.model)
                .filter(
                    and_(
                        self.model.event_id == event_id, self.model.guest_email == email
                    )
                )
                .first()
            )
        return None

    def get_multi_by_event(
        self, db: Session, *, event_id: str, skip: int = 0, limit: int = 100
    ) -> list[Registration]:
        """
        Fetches registrations for a specific event. The user details will be
        resolved by the GraphQL gateway, so we don't need to eager-load them here.
        """
        return (
            db.query(self.model)
            .filter(self.model.event_id == event_id)
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_count_by_event(self, db: Session, *, event_id: str) -> int:
        """
        Counts the number of registrations for a specific event.
        """
        return db.query(self.model).filter(self.model.event_id == event_id).count()

    def create_for_event(
        self, db: Session, *, obj_in: RegistrationCreate, event_id: str
    ) -> Registration:
        """
        Creates a registration and generates a unique ticket code.
        """
        create_data = {}
        if obj_in.user_id:
            create_data["user_id"] = obj_in.user_id
        else:
            create_data["guest_email"] = obj_in.email
            create_data["guest_name"] = f"{obj_in.first_name} {obj_in.last_name}"

        # Generate a unique ticket code
        while True:
            ticket_code = generate_ticket_code()
            if (
                not db.query(Registration)
                .filter(Registration.ticket_code == ticket_code)
                .first()
            ):
                break

        db_obj = self.model(**create_data, event_id=event_id, ticket_code=ticket_code)
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj


registration = CRUDRegistration(Registration)
