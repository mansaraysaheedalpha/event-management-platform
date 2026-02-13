# app/constants/rsvp.py
"""
Constants for Session RSVP status values.

Provides type-safe constants to replace hardcoded strings throughout the codebase.
"""


class RsvpStatus:
    """Session RSVP status values."""
    CONFIRMED = "CONFIRMED"
    CANCELLED = "CANCELLED"

    @classmethod
    def all_values(cls) -> list[str]:
        """Return all valid status values."""
        return [cls.CONFIRMED, cls.CANCELLED]

    @classmethod
    def is_valid(cls, status: str) -> bool:
        """Check if a status value is valid."""
        return status in cls.all_values()
