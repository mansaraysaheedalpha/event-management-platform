# app/services/offer_helpers.py
"""
Helper functions for offer-related operations.
"""
import logging
from typing import Optional
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

logger = logging.getLogger(__name__)


def verify_event_access(
    db: Session,
    event_id: str,
    organization_id: str
) -> bool:
    """
    Verify that an event belongs to the organization.

    Args:
        db: Database session
        event_id: Event ID to check
        organization_id: Organization ID making the request

    Returns: True if access granted

    Raises: HTTPException if access denied
    """
    from app.models.event import Event

    event = db.query(Event).filter(Event.id == event_id).first()

    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Event not found"
        )

    if event.organization_id != organization_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this event"
        )

    return True


def get_user_ticket_tier(
    db: Session,
    user_id: str,
    event_id: str
) -> Optional[str]:
    """
    Get the ticket tier for a user's registration to an event.

    Args:
        db: Database session
        user_id: User ID
        event_id: Event ID

    Returns: Ticket tier name or None if not registered
    """
    try:
        # Try to import ticket-related models
        # This may fail if ticket management tables don't exist yet
        from app.models.ticket import Ticket
        from app.models.ticket_type import TicketType

        # Find user's ticket for this event
        ticket = db.query(Ticket).join(TicketType).filter(
            Ticket.user_id == user_id,
            TicketType.event_id == event_id,
            Ticket.status.in_(["ACTIVE", "CHECKED_IN"])
        ).first()

        if ticket and ticket.ticket_type:
            return ticket.ticket_type.name

        return None

    except ImportError:
        # Ticket management not available
        logger.warning("Ticket management models not available")
        return None
    except Exception as e:
        logger.error(f"Error getting user ticket tier: {str(e)}")
        return None


def check_user_registered_for_event(
    db: Session,
    user_id: str,
    event_id: str
) -> bool:
    """
    Check if a user is registered for an event.

    Args:
        db: Database session
        user_id: User ID
        event_id: Event ID

    Returns: True if registered, False otherwise
    """
    try:
        from app.models.registration import Registration

        registration = db.query(Registration).filter(
            Registration.user_id == user_id,
            Registration.event_id == event_id,
            Registration.status == "CONFIRMED"
        ).first()

        return registration is not None

    except ImportError:
        # Registration model not available
        logger.warning("Registration model not available")
        return True  # Allow access if we can't check
    except Exception as e:
        logger.error(f"Error checking event registration: {str(e)}")
        return True  # Allow access on error


def calculate_offer_discount_percentage(
    price: float,
    original_price: Optional[float]
) -> int:
    """
    Calculate discount percentage for display.

    Args:
        price: Current price
        original_price: Original price (before discount)

    Returns: Discount percentage (0-100)
    """
    if not original_price or original_price <= price:
        return 0

    discount = ((original_price - price) / original_price) * 100
    return int(round(discount))


def validate_offer_targeting(
    offer,
    session_id: Optional[str] = None,
    user_ticket_tier: Optional[str] = None
) -> tuple[bool, Optional[str]]:
    """
    Validate if an offer's targeting rules match the current context.

    Args:
        offer: Offer model instance
        session_id: Current session ID (if in a session context)
        user_ticket_tier: User's ticket tier (if authenticated)

    Returns: (is_match, reason_if_not)
    """
    # Check session targeting
    if offer.target_sessions and session_id:
        if session_id not in offer.target_sessions:
            return False, "Offer not available for this session"

    # Check ticket tier targeting
    if offer.target_ticket_tiers and user_ticket_tier:
        if user_ticket_tier not in offer.target_ticket_tiers:
            return False, f"Offer only available for {', '.join(offer.target_ticket_tiers)} tickets"

    return True, None


def format_offer_for_display(offer) -> dict:
    """
    Format offer for frontend display with computed fields.

    Args:
        offer: Offer model instance

    Returns: Dict with formatted offer data
    """
    return {
        "id": offer.id,
        "title": offer.title,
        "description": offer.description,
        "price": offer.price,
        "original_price": offer.original_price,
        "currency": offer.currency,
        "discount_percentage": calculate_offer_discount_percentage(
            offer.price,
            offer.original_price
        ),
        "image_url": offer.image_url,
        "offer_type": offer.offer_type,
        "placement": offer.placement,
        "inventory_available": offer.inventory_available,
        "has_limited_inventory": offer.inventory_total is not None,
        "expires_at": offer.expires_at.isoformat() if offer.expires_at else None,
        "is_available": offer.is_available,
    }
