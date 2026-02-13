# app/api/v1/endpoints/offers.py
import json
import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Request, Header
from sqlalchemy.orm import Session

from app.api import deps
from app.db.session import get_db
from app.crud import crud_offer
from app.crud.crud_offer_purchase import offer_purchase
from app.schemas.offer import (
    OfferCreate,
    OfferUpdate,
    OfferResponse,
    Offer,
    OfferPurchaseCreate,
    OfferPurchaseResponse,
    OfferAvailabilityResponse,
    InventoryStatus
)
from app.schemas.token import TokenPayload
from app.services.offer_stripe_service import offer_stripe_service
from app.services.offer_reservation_service import offer_reservation_service
from app.services.offer_helpers import (
    verify_event_access,
    get_user_ticket_tier,
    validate_offer_targeting,
    check_user_registered_for_event
)
from app.core.config import settings

router = APIRouter(tags=["Offers"])
logger = logging.getLogger(__name__)


# ==================== Helper Functions ====================

def check_rate_limit(
    user_id: str,
    limit: int = settings.PURCHASE_RATE_LIMIT,
    window: int = settings.PURCHASE_RATE_WINDOW_SECONDS,
) -> None:
    """
    Check if user has exceeded rate limit for purchases.

    Args:
        user_id: User ID to check
        limit: Maximum number of requests allowed (default: 10)
        window: Time window in seconds (default: 60)

    Raises:
        HTTPException: If rate limit exceeded
    """
    if not offer_reservation_service:
        # Skip rate limiting if Redis unavailable
        return

    try:
        key = f"rate_limit:purchase:{user_id}"
        current_count = offer_reservation_service.redis.get(key)

        if current_count is None:
            # First request in window
            offer_reservation_service.redis.setex(key, window, 1)
        else:
            count = int(current_count)
            if count >= limit:
                logger.warning(
                    "Rate limit exceeded for purchase endpoint",
                    extra={
                        "user_id": user_id,
                        "current_count": count,
                        "limit": limit,
                        "window_seconds": window
                    }
                )
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=f"Too many purchase attempts. Please try again in {window} seconds."
                )
            # Increment counter
            offer_reservation_service.redis.incr(key)
    except HTTPException:
        raise
    except Exception as e:
        logger.warning(
            "Rate limit check failed",
            extra={"user_id": user_id, "error": str(e)},
            exc_info=True
        )
        # Don't block request if rate limiting fails


def build_offer_response(offer) -> dict:
    """Convert offer model to response dict with inventory status."""
    return {
        **offer.__dict__,
        "inventory": {
            "total": offer.inventory_total,
            "available": offer.inventory_available,
            "sold": offer.inventory_sold,
            "reserved": offer.inventory_reserved
        },
        "is_available": offer.is_available,
        "target_sessions": offer.target_sessions or [],
        "target_ticket_tiers": offer.target_ticket_tiers or [],
    }


# ==================== Endpoints ====================

@router.post(
    "/",
    response_model=OfferResponse,
    status_code=status.HTTP_201_CREATED
)
def create_offer(
    offer_in: OfferCreate,
    db: Session = Depends(get_db),
    current_user: TokenPayload = Depends(deps.get_current_user),
):
    """
    Create a new offer for an event.

    Business Logic:
    1. Validate user has permission to manage event
    2. Create Stripe Product and Price
    3. Insert offer into database
    4. Return created offer with Stripe IDs
    """
    # Verify user has access to the event
    verify_event_access(db, offer_in.event_id, current_user.org_id)

    # Create offer first (without Stripe IDs)
    offer = crud_offer.offer.create_with_organization(
        db,
        obj_in=offer_in,
        org_id=current_user.org_id
    )

    # Create Stripe Product
    stripe_product_id = offer_stripe_service.create_product(
        offer_id=offer.id,
        title=offer.title,
        description=offer.description,
        image_url=offer.image_url
    )

    if stripe_product_id:
        # Create Stripe Price
        stripe_price_id = offer_stripe_service.create_price(
            product_id=stripe_product_id,
            price=offer.price,
            currency=offer.currency,
            offer_id=offer.id
        )

        # Update offer with Stripe IDs
        if stripe_price_id:
            offer.stripe_product_id = stripe_product_id
            offer.stripe_price_id = stripe_price_id
            db.commit()
            db.refresh(offer)

    return build_offer_response(offer)


@router.get(
    "/events/{event_id}",
    response_model=List[OfferResponse]
)
def get_event_offers(
    event_id: str,
    placement: Optional[str] = None,
    session_id: Optional[str] = None,
    active_only: bool = True,
    db: Session = Depends(get_db),
    current_user: TokenPayload = Depends(deps.get_current_user),
):
    """
    Get all offers for an event with optional filtering.

    Query Logic:
    - Filter by placement (CHECKOUT, IN_EVENT, etc.)
    - Filter by session_id (offers targeting specific session)
    - Filter by active status and expiration date
    - Order by: created_at DESC
    """
    # Verify organizer has access to the event
    verify_event_access(db, event_id, current_user.org_id)

    offers = crud_offer.offer.get_multi_by_event(
        db,
        event_id=event_id,
        active_only=active_only,
        placement=placement
    )

    # If session_id provided, filter by targeting
    if session_id:
        offers = [
            offer for offer in offers
            if not offer.target_sessions or session_id in offer.target_sessions
        ]

    return [build_offer_response(offer) for offer in offers]


@router.get(
    "/events/{event_id}/active",
    response_model=List[OfferResponse]
)
def get_active_offers_for_attendee(
    event_id: str,
    session_id: Optional[str] = None,
    placement: str = "IN_EVENT",
    db: Session = Depends(get_db),
    current_user: Optional[TokenPayload] = Depends(deps.get_current_user_optional),
):
    """
    PUBLIC endpoint: Get active offers that should be shown to an attendee.

    Filtering:
    1. is_active = true AND is_archived = false
    2. NOW() BETWEEN starts_at AND (expires_at OR infinity)
    3. inventory_available > 0 (if inventory tracking enabled)
    4. placement = <requested_placement>
    5. Targeting rules match (session, ticket tier if user authenticated)

    Personalization (if user authenticated):
    - Check user's ticket tier
    - Filter by target_ticket_tiers if specified
    - Exclude already purchased offers (optional)
    """
    offers = crud_offer.offer.get_active_offers(
        db,
        event_id=event_id,
        placement=placement,
        session_id=session_id
    )

    # Filter by user's ticket tier if authenticated
    if current_user:
        user_tier = get_user_ticket_tier(db, current_user.sub, event_id)

        filtered_offers = []
        for offer in offers:
            # Check targeting rules
            is_match, _ = validate_offer_targeting(
                offer,
                session_id=session_id,
                user_ticket_tier=user_tier
            )

            if is_match:
                filtered_offers.append(offer)

        offers = filtered_offers

    return [build_offer_response(offer) for offer in offers]


@router.post(
    "/{offer_id}/check-availability",
    response_model=OfferAvailabilityResponse
)
def check_offer_availability(
    offer_id: str,
    quantity: int = 1,
    db: Session = Depends(get_db),
):
    """
    Check if an offer is available for purchase.
    Public endpoint - no auth required.
    """
    available, reason = crud_offer.offer.check_availability(
        db,
        offer_id=offer_id,
        quantity=quantity
    )

    offer = crud_offer.offer.get(db, id=offer_id)

    return {
        "available": available,
        "reason": reason,
        "inventory_available": offer.inventory_available if offer else 0
    }


@router.post(
    "/purchase",
    status_code=status.HTTP_200_OK
)
def purchase_offer(
    purchase_data: OfferPurchaseCreate,
    db: Session = Depends(get_db),
    current_user: TokenPayload = Depends(deps.get_current_user),
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
):
    """
    Add offer to cart / create checkout session with offer.

    Flow:
    1. Validate offer is available (inventory check)
    2. Reserve inventory (increment inventory_reserved)
    3. Create or update checkout session
    4. Add offer as line item to Stripe checkout
    5. Return checkout URL

    Inventory Reservation:
    - Use Redis for temporary reservation with TTL (15 minutes)
    - Key: offer_reservation:{checkout_session_id}:{offer_id}
    - On checkout complete: move reserved → sold
    - On checkout expire: release reserved inventory

    Response:
    {
      "checkout_session_id": "cs_xxx",
      "stripe_checkout_url": "https://checkout.stripe.com/...",
      "order": { ... }
    }
    """
    # Check rate limit (10 purchases per minute)
    check_rate_limit(user_id=current_user.sub, limit=10, window=60)

    # SECURITY: Verify offer exists and user has access to the event
    offer_obj = crud_offer.offer.get(db, id=purchase_data.offer_id)
    if not offer_obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Offer not found"
        )

    # Verify the event is public or the user is registered
    from app.models.event import Event
    event = db.query(Event).filter(Event.id == offer_obj.event_id).first()
    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Event not found"
        )

    if not event.is_public:
        is_registered = check_user_registered_for_event(
            db, user_id=current_user.sub, event_id=offer_obj.event_id
        )
        if not is_registered:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You must be registered for this event to purchase offers"
            )

    # Validate quantity bounds
    if purchase_data.quantity < 1 or purchase_data.quantity > 20:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Quantity must be between 1 and 20"
        )

    # Check for idempotent request
    if idempotency_key and offer_reservation_service:
        try:
            cache_key = f"purchase_idempotency:{current_user.sub}:{idempotency_key}"
            cached_result = offer_reservation_service.redis.get(cache_key)
            if cached_result:
                logger.info(f"Returning cached purchase result for idempotency key {idempotency_key}")
                return json.loads(cached_result)
        except Exception as e:
            logger.warning(f"Failed to check idempotency cache: {str(e)}")
            # Continue with normal flow if cache check fails

    # Atomically check availability and reserve inventory under row lock
    # to prevent race conditions where two requests both pass availability
    # checks then both try to reserve the same inventory
    offer, error_reason = crud_offer.offer.check_and_reserve_inventory(
        db,
        offer_id=purchase_data.offer_id,
        quantity=purchase_data.quantity
    )

    if not offer:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_reason or "Failed to reserve inventory"
        )

    # Create Stripe checkout session
    checkout_session = offer_stripe_service.create_checkout_session(
        price_id=offer.stripe_price_id,
        quantity=purchase_data.quantity,
        success_url=f"{settings.FRONTEND_URL}/events/{offer.event_id}/offers/success?session_id={{CHECKOUT_SESSION_ID}}",
        cancel_url=f"{settings.FRONTEND_URL}/events/{offer.event_id}/offers",
        metadata={
            "offer_id": str(offer.id),
            "user_id": str(current_user.sub),
            "quantity": str(purchase_data.quantity),
            "event_id": str(offer.event_id)
        }
    )

    # Check if Stripe checkout session creation failed
    if not checkout_session:
        # Rollback the inventory reservation
        crud_offer.offer.release_inventory(
            db,
            offer_id=str(offer.id),
            quantity=purchase_data.quantity
        )
        logger.error(
            "Failed to create Stripe checkout session",
            extra={
                "offer_id": str(offer.id),
                "event_id": str(offer.event_id),
                "user_id": str(current_user.sub),
                "quantity": purchase_data.quantity,
                "price": offer.price,
                "action": "purchase_rollback"
            }
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Payment provider temporarily unavailable. Please try again."
        )

    # Store reservation in Redis with 15-minute TTL (if available)
    if offer_reservation_service:
        try:
            offer_reservation_service.create_reservation(
                checkout_session_id=checkout_session["session_id"],
                offer_id=str(offer.id),
                quantity=purchase_data.quantity,
                user_id=str(current_user.sub)
            )
        except Exception as e:
            logger.warning(f"Failed to create Redis reservation: {str(e)}")
            # Continue anyway - webhook will handle confirmation
    else:
        logger.warning("Redis unavailable, reservation not cached")

    # Prepare response
    response = {
        "message": "Checkout session created",
        "offer_id": offer.id,
        "quantity": purchase_data.quantity,
        "total_price": offer.price * purchase_data.quantity,
        "checkout_session_id": checkout_session["session_id"],
        "stripe_checkout_url": checkout_session["url"],
    }

    # Cache result for idempotency (30 day TTL — must outlive refund window)
    if idempotency_key and offer_reservation_service:
        try:
            cache_key = f"purchase_idempotency:{current_user.sub}:{idempotency_key}"
            offer_reservation_service.redis.setex(
                cache_key,
                2592000,  # 30 days
                json.dumps(response)
            )
        except Exception as e:
            logger.warning(f"Failed to cache purchase result: {str(e)}")
            # Don't fail the request if caching fails

    return response


@router.get(
    "/my-purchases/{event_id}",
    response_model=List[OfferPurchaseResponse]
)
def get_my_purchased_offers(
    event_id: str,
    db: Session = Depends(get_db),
    current_user: TokenPayload = Depends(deps.get_current_user),
):
    """
    Get all offers purchased by current user for an event.

    Response includes:
    - Offer details
    - Purchase details (quantity, price, date)
    - Fulfillment status
    - Digital content access (if applicable)
    """
    purchases = offer_purchase.get_user_purchases(
        db,
        user_id=current_user.sub,
        event_id=event_id
    )

    return purchases


@router.patch(
    "/{offer_id}",
    response_model=OfferResponse
)
def update_offer(
    offer_id: str,
    update_data: OfferUpdate,
    db: Session = Depends(get_db),
    current_user: TokenPayload = Depends(deps.get_current_user),
):
    """
    Update an existing offer.

    Validation:
    - Cannot change price if offer has purchases (create new offer instead)
    - If changing inventory_total, ensure >= (inventory_sold + inventory_reserved)
    - Update Stripe Price if price changed
    """
    offer = crud_offer.offer.get(db, id=offer_id)

    if not offer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Offer not found"
        )

    # Check authorization
    if offer.organization_id != current_user.org_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized"
        )

    # Validate inventory changes
    if update_data.inventory_total is not None:
        if update_data.inventory_total < (offer.inventory_sold + offer.inventory_reserved):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"inventory_total must be at least {offer.inventory_sold + offer.inventory_reserved}"
            )

    # Check if offer has purchases before allowing price changes
    if update_data.price is not None and update_data.price != offer.price:
        if offer.inventory_sold > 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot change price for offer with existing purchases. Create a new offer instead."
            )

        # Update Stripe price if price changed
        if offer.stripe_price_id and offer.stripe_product_id:
            new_stripe_price_id = offer_stripe_service.create_price(
                product_id=offer.stripe_product_id,
                price=update_data.price,
                currency=offer.currency,
                offer_id=str(offer_id)
            )
            update_data.stripe_price_id = new_stripe_price_id

    updated_offer = crud_offer.offer.update(
        db,
        db_obj=offer,
        obj_in=update_data
    )

    return build_offer_response(updated_offer)


@router.delete(
    "/{offer_id}",
    status_code=status.HTTP_204_NO_CONTENT
)
def archive_offer(
    offer_id: str,
    db: Session = Depends(get_db),
    current_user: TokenPayload = Depends(deps.get_current_user),
):
    """
    Soft delete (archive) an offer.
    Set is_archived = true, is_active = false
    """
    offer = crud_offer.offer.get(db, id=offer_id)

    if not offer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Offer not found"
        )

    # Check authorization
    if offer.organization_id != current_user.org_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized"
        )

    crud_offer.offer.archive(db, id=offer_id)

    return None


@router.get(
    "/{offer_id}",
    response_model=OfferResponse
)
def get_offer(
    offer_id: str,
    db: Session = Depends(get_db),
    current_user: TokenPayload = Depends(deps.get_current_user),
):
    """Get a single offer by ID."""
    offer = crud_offer.offer.get(db, id=offer_id)

    if not offer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Offer not found"
        )

    # Check authorization
    if offer.organization_id != current_user.org_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized"
        )

    return build_offer_response(offer)


# ==================== Legacy Endpoints (Backward Compatibility) ====================

@router.post(
    "/organizations/{orgId}/offers",
    response_model=Offer,
    status_code=status.HTTP_201_CREATED,
    deprecated=True
)
def create_offer_legacy(
    orgId: str,
    offer_in: OfferCreate,
    db: Session = Depends(get_db),
    current_user: TokenPayload = Depends(deps.get_current_user),
):
    """
    [DEPRECATED] Create a new offer for an organization.
    Use POST / instead.
    """
    if current_user.org_id != orgId:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized"
        )
    return crud_offer.offer.create_with_organization(db, obj_in=offer_in, org_id=orgId)


@router.get(
    "/organizations/{orgId}/offers",
    response_model=List[Offer],
    deprecated=True
)
def list_offers_legacy(
    orgId: str,
    db: Session = Depends(get_db),
    current_user: TokenPayload = Depends(deps.get_current_user),
):
    """
    [DEPRECATED] List all offers for an organization.
    Use GET /events/{event_id} instead.
    """
    if current_user.org_id != orgId:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized"
        )
    return crud_offer.offer.get_multi_by_organization(db, org_id=orgId)
