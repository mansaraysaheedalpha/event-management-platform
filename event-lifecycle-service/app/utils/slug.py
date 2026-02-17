# app/utils/slug.py
import re
import unicodedata
from sqlalchemy.orm import Session
from app.models.venue import Venue


def generate_slug(name: str, db: Session, exclude_venue_id: str | None = None) -> str:
    """
    Generate a URL-friendly slug from a venue name.
    Handles unicode transliteration, duplicate detection, and edge cases.

    Args:
        name: The venue name to slugify.
        db: Database session for uniqueness checks.
        exclude_venue_id: Venue ID to exclude from duplicate check (for updates).

    Returns:
        A unique slug string.
    """
    # Transliterate unicode to ASCII (e.g., "Café" -> "Cafe")
    normalized = unicodedata.normalize("NFKD", name)
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii")

    # Lowercase
    slug = ascii_text.lower()

    # Replace spaces and special chars with hyphens
    slug = re.sub(r"[^a-z0-9]+", "-", slug)

    # Remove leading/trailing hyphens
    slug = slug.strip("-")

    # Collapse multiple hyphens
    slug = re.sub(r"-+", "-", slug)

    # Ensure non-empty
    if not slug:
        slug = "venue"

    # Check uniqueness
    base_slug = slug
    counter = 1
    while True:
        query = db.query(Venue.id).filter(Venue.slug == slug)
        if exclude_venue_id:
            query = query.filter(Venue.id != exclude_venue_id)
        if not query.first():
            break
        counter += 1
        slug = f"{base_slug}-{counter}"

    return slug
