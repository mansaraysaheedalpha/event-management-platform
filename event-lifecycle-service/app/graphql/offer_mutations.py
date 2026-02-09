# app/graphql/offer_mutations.py
"""
GraphQL mutations for Offer management.

Provides mutation endpoints for:
- Creating offers
- Updating offers
- Deleting/archiving offers
- Purchasing offers
"""
import strawberry
from typing import Optional, List
from strawberry.types import Info
from fastapi import HTTPException
from datetime import datetime
import stripe
import os
import logging

from .. import crud
from ..core.config import settings
from ..models.offer import Offer
from ..schemas.offer import OfferCreate, OfferUpdate
from .types import OfferType
from .payment_types import MoneyType
from ..utils.security import (
    validate_offer_input,
    validate_url,
    validate_quantity,
    validate_string_length,
    validate_array_size,
    validate_positive_number,
    validate_enum,
    sanitize_error_message,
    VALID_PLACEMENTS,
    VALID_CURRENCIES,
    MAX_PRICE,
)

logger = logging.getLogger(__name__)

# Configure Stripe
stripe.api_key = os.environ.get("STRIPE_SECRET_KEY")


# Input Types
@strawberry.input
class OfferCreateInput:
    """Input for creating a new offer."""
    event_id: str
    title: str
    description: Optional[str] = None
    offer_type: str  # TICKET_UPGRADE, MERCHANDISE, EXCLUSIVE_CONTENT, SERVICE
    price: float
    original_price: Optional[float] = None
    currency: Optional[str] = "USD"
    image_url: Optional[str] = None
    inventory_total: Optional[int] = None  # None = unlimited
    placement: Optional[str] = "IN_EVENT"  # CHECKOUT, POST_PURCHASE, IN_EVENT, EMAIL
    target_sessions: Optional[List[str]] = None
    target_ticket_tiers: Optional[List[str]] = None
    starts_at: Optional[str] = None  # ISO datetime string
    expires_at: Optional[str] = None  # ISO datetime string
    is_active: Optional[bool] = True


@strawberry.input
class OfferUpdateInput:
    """Input for updating an existing offer."""
    title: Optional[str] = None
    description: Optional[str] = None
    price: Optional[float] = None
    original_price: Optional[float] = None
    image_url: Optional[str] = None
    inventory_total: Optional[int] = None
    placement: Optional[str] = None
    target_sessions: Optional[List[str]] = None
    target_ticket_tiers: Optional[List[str]] = None
    starts_at: Optional[str] = None
    expires_at: Optional[str] = None
    is_active: Optional[bool] = None


# Response Types
@strawberry.type
class OfferOrderType:
    """Order information after purchase."""
    id: str
    orderNumber: Optional[str]
    status: str
    totalAmount: MoneyType


@strawberry.type
class OfferPurchaseResponse:
    """Response from purchasing an offer."""
    checkoutSessionId: Optional[str]
    stripeCheckoutUrl: Optional[str]
    order: Optional[OfferOrderType]


def _convert_offer_to_type(offer: Offer) -> OfferType:
    """Convert Offer model to GraphQL type."""
    return OfferType(
        id=offer.id,
        organization_id=offer.organization_id,
        event_id=offer.event_id,
        title=offer.title,
        description=offer.description,
        price=offer.price,
        original_price=offer.original_price,
        currency=offer.currency,
        offer_type=offer.offer_type,
        image_url=offer.image_url,
        expires_at=offer.expires_at,
        is_archived=offer.is_archived,
    )


class OfferMutations:
    """Offer mutation resolvers"""

    @staticmethod
    def create_offer(offer_in: OfferCreateInput, info: Info) -> OfferType:
        """
        Create a new offer for an event.

        Requires authentication and organizer access to the event.
        """
        user = info.context.user
        if not user:
            raise HTTPException(status_code=401, detail="Authentication required")

        db = info.context.db
        org_id = user.get("orgId")

        if not org_id:
            raise HTTPException(status_code=403, detail="Organization membership required")

        # Verify event ownership
        event = crud.event.get(db, id=offer_in.event_id)
        if not event:
            raise HTTPException(status_code=404, detail="Event not found")

        if event.organization_id != org_id:
            raise HTTPException(
                status_code=403,
                detail="Not authorized to create offers for this event"
            )

        # SECURITY: Validate all input fields
        validation_errors = validate_offer_input(offer_in)
        if validation_errors:
            raise HTTPException(
                status_code=400,
                detail=f"Validation failed: {'; '.join(validation_errors)}"
            )

        # Parse dates
        starts_at = None
        expires_at = None
        if offer_in.starts_at:
            starts_at = datetime.fromisoformat(offer_in.starts_at.replace("Z", "+00:00"))
        if offer_in.expires_at:
            expires_at = datetime.fromisoformat(offer_in.expires_at.replace("Z", "+00:00"))

        # Build offer create schema
        offer_create = OfferCreate(
            event_id=offer_in.event_id,
            title=offer_in.title,
            description=offer_in.description,
            offer_type=offer_in.offer_type,
            price=offer_in.price,
            original_price=offer_in.original_price,
            currency=offer_in.currency or "USD",
            image_url=offer_in.image_url,
            inventory_total=offer_in.inventory_total,
            placement=offer_in.placement or "IN_EVENT",
            target_sessions=offer_in.target_sessions or [],
            target_ticket_tiers=offer_in.target_ticket_tiers or [],
            starts_at=starts_at,
            expires_at=expires_at,
        )

        # Create the offer with organization ID
        offer = crud.offer.create_with_organization(db, obj_in=offer_create, org_id=org_id)
        offer.is_active = offer_in.is_active if offer_in.is_active is not None else True
        db.commit()
        db.refresh(offer)

        return _convert_offer_to_type(offer)

    @staticmethod
    def update_offer(id: str, offer_in: OfferUpdateInput, info: Info) -> OfferType:
        """
        Update an existing offer.

        Requires authentication and organizer access.
        """
        user = info.context.user
        if not user:
            raise HTTPException(status_code=401, detail="Authentication required")

        db = info.context.db
        org_id = user.get("orgId")

        if not org_id:
            raise HTTPException(status_code=403, detail="Organization membership required")

        # Get existing offer
        offer = crud.offer.get(db, id=id)
        if not offer:
            raise HTTPException(status_code=404, detail="Offer not found")

        if offer.organization_id != org_id:
            raise HTTPException(status_code=403, detail="Not authorized to update this offer")

        # SECURITY: Validate fields if provided
        if offer_in.image_url is not None:
            valid, err = validate_url(offer_in.image_url, "image_url", allow_http=True)
            if not valid:
                raise HTTPException(status_code=400, detail=err)

        if offer_in.title is not None:
            valid, err = validate_string_length(offer_in.title, "title")
            if not valid:
                raise HTTPException(status_code=400, detail=err)

        if offer_in.description is not None:
            valid, err = validate_string_length(offer_in.description, "description")
            if not valid:
                raise HTTPException(status_code=400, detail=err)

        if offer_in.price is not None:
            valid, err = validate_positive_number(offer_in.price, "price", MAX_PRICE)
            if not valid:
                raise HTTPException(status_code=400, detail=err)

        if offer_in.placement is not None:
            valid, err = validate_enum(offer_in.placement, "placement", VALID_PLACEMENTS)
            if not valid:
                raise HTTPException(status_code=400, detail=err)

        if offer_in.target_sessions is not None:
            valid, err = validate_array_size(offer_in.target_sessions, "target_sessions")
            if not valid:
                raise HTTPException(status_code=400, detail=err)

        if offer_in.target_ticket_tiers is not None:
            valid, err = validate_array_size(offer_in.target_ticket_tiers, "target_ticket_tiers")
            if not valid:
                raise HTTPException(status_code=400, detail=err)

        # Build update data
        update_kwargs = {}
        if offer_in.title is not None:
            update_kwargs["title"] = offer_in.title
        if offer_in.description is not None:
            update_kwargs["description"] = offer_in.description
        if offer_in.price is not None:
            update_kwargs["price"] = offer_in.price
        if offer_in.original_price is not None:
            update_kwargs["original_price"] = offer_in.original_price
        if offer_in.image_url is not None:
            update_kwargs["image_url"] = offer_in.image_url
        if offer_in.inventory_total is not None:
            update_kwargs["inventory_total"] = offer_in.inventory_total
        if offer_in.placement is not None:
            update_kwargs["placement"] = offer_in.placement
        if offer_in.target_sessions is not None:
            update_kwargs["target_sessions"] = offer_in.target_sessions
        if offer_in.target_ticket_tiers is not None:
            update_kwargs["target_ticket_tiers"] = offer_in.target_ticket_tiers
        if offer_in.starts_at is not None:
            update_kwargs["starts_at"] = datetime.fromisoformat(offer_in.starts_at.replace("Z", "+00:00"))
        if offer_in.expires_at is not None:
            update_kwargs["expires_at"] = datetime.fromisoformat(offer_in.expires_at.replace("Z", "+00:00"))
        if offer_in.is_active is not None:
            update_kwargs["is_active"] = offer_in.is_active

        if not update_kwargs:
            return _convert_offer_to_type(offer)

        offer_update = OfferUpdate(**update_kwargs)

        # Update offer using CRUD
        updated_offer = crud.offer.update(db, db_obj=offer, obj_in=offer_update)

        return _convert_offer_to_type(updated_offer)

    @staticmethod
    def delete_offer(id: str, info: Info) -> bool:
        """
        Delete (archive) an offer.

        Requires authentication and organizer access.
        """
        user = info.context.user
        if not user:
            raise HTTPException(status_code=401, detail="Authentication required")

        db = info.context.db
        org_id = user.get("orgId")

        if not org_id:
            raise HTTPException(status_code=403, detail="Organization membership required")

        # Get existing offer
        offer = crud.offer.get(db, id=id)
        if not offer:
            raise HTTPException(status_code=404, detail="Offer not found")

        if offer.organization_id != org_id:
            raise HTTPException(status_code=403, detail="Not authorized to delete this offer")

        # Archive instead of hard delete
        crud.offer.update(db, db_obj=offer, obj_in={"is_archived": True, "is_active": False})

        return True

    @staticmethod
    async def purchase_offer(
        offer_id: str,
        quantity: int,
        info: Info
    ) -> OfferPurchaseResponse:
        """
        Purchase an offer - creates a Stripe checkout session.

        Requires authentication.
        """
        user = info.context.user
        if not user:
            raise HTTPException(status_code=401, detail="Authentication required")

        db = info.context.db
        user_id = user.get("sub")
        user_email = user.get("email")

        if not user_email:
            raise HTTPException(status_code=400, detail="User email is required for purchase")

        # SECURITY: Validate quantity
        valid, err = validate_quantity(quantity)
        if not valid:
            raise HTTPException(status_code=400, detail=err)

        # Get the offer
        offer = crud.offer.get(db, id=offer_id)
        if not offer:
            raise HTTPException(status_code=404, detail="Offer not found")

        # Check availability
        is_available, reason = crud.offer.check_availability(db, offer_id=offer_id, quantity=quantity)
        if not is_available:
            raise HTTPException(status_code=400, detail=reason)

        # Reserve inventory
        reserved_offer = crud.offer.reserve_inventory(db, offer_id=offer_id, quantity=quantity)
        if not reserved_offer:
            raise HTTPException(status_code=400, detail="Failed to reserve inventory")

        # Get the event
        event = crud.event.get(db, id=offer.event_id)
        if not event:
            raise HTTPException(status_code=404, detail="Event not found")

        # Calculate total
        total_amount = int(offer.price * quantity * 100)  # Convert to cents

        try:
            # Create Stripe checkout session
            success_url = settings.FRONTEND_URL
            cancel_url = settings.FRONTEND_URL

            checkout_session = stripe.checkout.Session.create(
                payment_method_types=["card"],
                line_items=[
                    {
                        "price_data": {
                            "currency": offer.currency.lower(),
                            "unit_amount": int(offer.price * 100),  # Cents
                            "product_data": {
                                "name": offer.title,
                                "description": offer.description or f"Offer for {event.name}",
                            },
                        },
                        "quantity": quantity,
                    }
                ],
                mode="payment",
                success_url=f"{success_url}/events/{event.id}?purchase=success&offer_id={offer_id}",
                cancel_url=f"{cancel_url}/events/{event.id}?purchase=cancelled&offer_id={offer_id}",
                customer_email=user_email,
                metadata={
                    "offer_id": offer_id,
                    "user_id": user_id,
                    "event_id": offer.event_id,
                    "quantity": str(quantity),
                    "type": "offer_purchase",
                },
            )

            # Create order record (would need order model for offers)
            return OfferPurchaseResponse(
                checkoutSessionId=checkout_session.id,
                stripeCheckoutUrl=checkout_session.url,
                order=OfferOrderType(
                    id=checkout_session.id,
                    orderNumber=None,
                    status="pending",
                    totalAmount=MoneyType(
                        amount=int(offer.price * quantity * 100),  # Convert to cents
                        currency=offer.currency,
                    ),
                ),
            )

        except stripe.error.StripeError as e:
            # Release inventory on failure
            crud.offer.release_inventory(db, offer_id=offer_id, quantity=quantity)
            # SECURITY: Log actual error, return sanitized message
            logger.error(f"Stripe error during offer purchase: {e}")
            raise HTTPException(status_code=400, detail=sanitize_error_message(e))
        except Exception as e:
            # Release inventory on failure
            crud.offer.release_inventory(db, offer_id=offer_id, quantity=quantity)
            # SECURITY: Log actual error, return generic message
            logger.error(f"Error during offer purchase: {e}")
            raise HTTPException(status_code=500, detail="Payment processing error. Please try again.")
