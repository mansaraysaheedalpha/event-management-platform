# app/graphql/dataloaders.py
"""
DataLoaders for batching and eliminating N+1 queries in GraphQL resolvers.

Each DataLoader batches multiple individual lookups into a single database query,
significantly reducing query overhead when resolving nested fields.
"""
from typing import List, Dict, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func, and_
from strawberry.dataloader import DataLoader

from app.models.venue import Venue
from app.models.offer import Offer
from app.models.registration import Registration


def batch_load_venues(keys: List[str], db: Session) -> List[Optional[Venue]]:
    """
    Batch load venues by IDs.

    Instead of N individual queries:
        SELECT * FROM venues WHERE id = 'venue1';
        SELECT * FROM venues WHERE id = 'venue2';
        ...

    Makes 1 query:
        SELECT * FROM venues WHERE id IN ('venue1', 'venue2', ...);
    """
    # Fetch all venues in one query
    venues = db.query(Venue).filter(Venue.id.in_(keys)).all()

    # Create lookup map
    venue_map: Dict[str, Venue] = {venue.id: venue for venue in venues}

    # Return in same order as keys (important for DataLoader contract)
    # Return raw ORM objects — Strawberry auto-maps them to VenueType
    return [venue_map.get(key) for key in keys]


def batch_load_registration_counts(keys: List[str], db: Session) -> List[int]:
    """
    Batch load registration counts by event IDs.

    Instead of N individual COUNT queries:
        SELECT COUNT(*) FROM registrations WHERE event_id = 'evt1' AND ...;
        SELECT COUNT(*) FROM registrations WHERE event_id = 'evt2' AND ...;

    Makes 1 query:
        SELECT event_id, COUNT(*) FROM registrations
        WHERE event_id IN ('evt1', 'evt2', ...) AND ...
        GROUP BY event_id;
    """
    # Batch count query
    results = (
        db.query(
            Registration.event_id,
            func.count(Registration.id).label("count")
        )
        .filter(
            Registration.event_id.in_(keys),
            Registration.is_archived == "false",
            Registration.status != "cancelled",
        )
        .group_by(Registration.event_id)
        .all()
    )

    # Create lookup map
    count_map: Dict[str, int] = {event_id: count for event_id, count in results}

    # Return in same order as keys, default to 0 if no registrations
    return [count_map.get(key, 0) for key in keys]


def batch_load_offers(keys: List[str], db: Session) -> List[Optional[Offer]]:
    """
    Batch load offers by IDs.

    Instead of N individual queries:
        SELECT * FROM offers WHERE id = 'offer1';
        SELECT * FROM offers WHERE id = 'offer2';
        ...

    Makes 1 query:
        SELECT * FROM offers WHERE id IN ('offer1', 'offer2', ...);
    """
    # Fetch all offers in one query
    offers = db.query(Offer).filter(Offer.id.in_(keys)).all()

    # Create lookup map
    offer_map: Dict[str, Offer] = {offer.id: offer for offer in offers}

    # Return in same order as keys
    # Return raw ORM objects — Strawberry auto-maps them to OfferType
    return [offer_map.get(key) for key in keys]


def batch_load_session_attendance_stats(keys: List[str], db: Session) -> List[Dict]:
    """
    Batch load virtual attendance stats by session IDs.

    Instead of N individual queries per session:
        SELECT COUNT(*), AVG(duration) FROM virtual_attendance WHERE session_id = 'session1';
        SELECT COUNT(*), AVG(duration) FROM virtual_attendance WHERE session_id = 'session2';
        ...

    Makes 1 query:
        SELECT session_id, COUNT(*), AVG(duration), ...
        FROM virtual_attendance
        WHERE session_id IN ('session1', 'session2', ...)
        GROUP BY session_id;
    """
    from app.models.virtual_attendance import VirtualAttendance

    # Batch stats query
    results = (
        db.query(
            VirtualAttendance.session_id,
            func.count(func.distinct(VirtualAttendance.user_id)).label("total_attendees"),
            func.avg(VirtualAttendance.duration_seconds).label("avg_duration"),
            func.max(VirtualAttendance.duration_seconds).label("max_duration"),
        )
        .filter(VirtualAttendance.session_id.in_(keys))
        .group_by(VirtualAttendance.session_id)
        .all()
    )

    # Create lookup map
    stats_map: Dict[str, Dict] = {
        session_id: {
            "total_attendees": total_attendees or 0,
            "avg_duration": int(avg_duration) if avg_duration else 0,
            "max_duration": max_duration or 0,
        }
        for session_id, total_attendees, avg_duration, max_duration in results
    }

    # Return in same order as keys, with default values if no data
    default_stats = {"total_attendees": 0, "avg_duration": 0, "max_duration": 0}
    return [stats_map.get(key, default_stats) for key in keys]


def create_dataloaders(db: Session) -> Dict[str, DataLoader]:
    """
    Factory function to create all DataLoaders for a GraphQL request.

    Called once per request in the GraphQL context getter.
    """
    return {
        "venue_loader": DataLoader(load_fn=lambda keys: batch_load_venues(keys, db)),
        "registration_count_loader": DataLoader(load_fn=lambda keys: batch_load_registration_counts(keys, db)),
        "offer_loader": DataLoader(load_fn=lambda keys: batch_load_offers(keys, db)),
        "session_stats_loader": DataLoader(load_fn=lambda keys: batch_load_session_attendance_stats(keys, db)),
    }
